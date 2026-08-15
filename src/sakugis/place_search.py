"""Brave-backed place descriptions and image discovery."""

from __future__ import annotations

import html
import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from sakugis.agent_models import Candidate
from sakugis.credentials import get_brave_api_key


BRAVE_SEARCH_BASE_URL = "https://api.search.brave.com/res/v1"
BRAVE_WEB_RESULT_LIMIT = 6
BRAVE_IMAGE_RESULT_LIMIT = 8
BRAVE_IMAGE_REQUEST_LIMIT = 24
BRAVE_IMAGE_PER_PAGE_LIMIT = 2
MAX_THUMBNAIL_BYTES = 2 * 1024 * 1024
SESSION_CACHE_TTL_SECONDS = 15 * 60
USER_AGENT = "SakuGIS/0.5.0 (+https://urbancomp.net)"

_NON_PLACE_IMAGE_HOST_MARKERS = (
    "amazon.",
    "aliexpress.",
    "ebay.",
    "hkairportshop.",
    "jd.com",
    "piececool.",
    "shop.",
    "store.",
    "taobao.",
    "tmall.",
    "walmart.",
)
_NON_PLACE_IMAGE_TEXT_MARKERS = (
    "42度",
    "52度",
    "500毫升",
    "白酒",
    "机场店",
    "积木",
    "酒瓶",
    "模型拼装",
    "模型套件",
    "拼图",
    "商品详情",
    "手办",
    "玩具",
    "纸模",
    "bottle",
    "buy online",
    "figurine",
    "liquor",
    "model kit",
    "paper model",
    "product listing",
    "puzzle",
    "shopping",
    "toy",
)


class PlaceSearchError(RuntimeError):
    """Safe error with a stable code for localized UI rendering."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class PlaceWebResult:
    title: str
    url: str
    description: str
    source: str


@dataclass(frozen=True)
class PlaceImageResult:
    title: str
    page_url: str
    thumbnail_url: str
    original_url: str
    source: str
    width: int = 0
    height: int = 0


@dataclass(frozen=True)
class PlaceDetails:
    candidate_id: str
    query: str
    web_results: List[PlaceWebResult] = field(default_factory=list)
    images: List[PlaceImageResult] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class MemoryPlaceCache:
    """Short-lived cache; explicit SGD saves may snapshot displayed material."""

    def __init__(self, ttl_seconds: int = SESSION_CACHE_TTL_SECONDS):
        self.ttl_seconds = max(1, int(ttl_seconds))
        self._values: Dict[str, Tuple[float, PlaceDetails]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[PlaceDetails]:
        with self._lock:
            stored = self._values.get(key)
            if stored is None:
                return None
            created_at, details = stored
            if time.monotonic() - created_at > self.ttl_seconds:
                self._values.pop(key, None)
                return None
            return details

    def set(self, key: str, value: PlaceDetails) -> None:
        with self._lock:
            if len(self._values) >= 64:
                oldest = min(
                    self._values,
                    key=lambda item: self._values[item][0],
                )
                self._values.pop(oldest, None)
            self._values[key] = (time.monotonic(), value)

    def clear(self) -> None:
        with self._lock:
            self._values.clear()


class BraveSearchClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = BRAVE_SEARCH_BASE_URL,
        timeout: int = 20,
        cache: Optional[MemoryPlaceCache] = None,
        opener: Optional[Callable[..., Any]] = None,
    ):
        self.api_key = api_key or get_brave_api_key()
        self.base_url = base_url.rstrip("/")
        self.timeout = max(1, int(timeout))
        self.cache = cache or MemoryPlaceCache()
        self.opener = opener or urllib.request.urlopen

    def search_place(
        self,
        candidate: Candidate,
        language: str,
        force_refresh: bool = False,
    ) -> PlaceDetails:
        query = build_place_query(candidate, language)
        cache_key = (
            f"{candidate.candidate_id}:{candidate.latitude:.5f}:"
            f"{candidate.longitude:.5f}:{language}:{query}"
        )
        if not force_refresh:
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached

        country = _country_parameter(candidate.country_code)
        search_language = "zh-hans" if language == "zh_CN" else "en"
        requests = {
            "web": (
                "/web/search",
                {
                    "q": query,
                    "count": BRAVE_WEB_RESULT_LIMIT,
                    "country": country,
                    "search_lang": search_language,
                    "safesearch": "moderate",
                    "spellcheck": "1",
                    "text_decorations": "0",
                },
            ),
            "images": (
                "/images/search",
                {
                    "q": _image_query(query, language),
                    "count": BRAVE_IMAGE_REQUEST_LIMIT,
                    "country": country,
                    "search_lang": search_language,
                    "safesearch": "strict",
                    "spellcheck": "1",
                },
            ),
        }
        payloads: Dict[str, Dict[str, Any]] = {}
        warnings: List[str] = []
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = {
                executor.submit(
                    self._request_json_with_fallback, route, params
                ): name
                for name, (route, params) in requests.items()
            }
            for future in as_completed(futures):
                name = futures[future]
                try:
                    payloads[name] = future.result()
                except PlaceSearchError as exc:
                    warnings.append(exc.code)

        if not payloads:
            raise PlaceSearchError(warnings[0] if warnings else "network")
        details = PlaceDetails(
            candidate_id=candidate.candidate_id,
            query=query,
            web_results=parse_web_results(payloads.get("web", {})),
            images=parse_image_results(payloads.get("images", {})),
            warnings=list(dict.fromkeys(warnings)),
        )
        self.cache.set(cache_key, details)
        return details

    def _request_json_with_fallback(
        self, route: str, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Retry conservative parameters for Brave country/language gaps."""
        try:
            return self._request_json(route, parameters)
        except PlaceSearchError as exc:
            if exc.code != "request":
                raise
        fallback = dict(parameters)
        fallback["country"] = "ALL"
        try:
            return self._request_json(route, fallback)
        except PlaceSearchError as exc:
            if exc.code != "request":
                raise
        fallback.pop("search_lang", None)
        return self._request_json(route, fallback)

    def fetch_thumbnail(self, url: str) -> bytes:
        parsed = urllib.parse.urlparse(url)
        if (
            parsed.scheme != "https"
            or parsed.hostname != "imgs.search.brave.com"
        ):
            raise PlaceSearchError("image_url")
        request = urllib.request.Request(url)
        request.add_header("Accept", "image/jpeg,image/png,image/webp")
        request.add_header("User-Agent", USER_AGENT)
        try:
            with self.opener(request, timeout=self.timeout) as response:
                content_type = str(
                    response.headers.get("Content-Type", "")
                ).casefold()
                if content_type and not content_type.startswith("image/"):
                    raise PlaceSearchError("image_format")
                content = response.read(MAX_THUMBNAIL_BYTES + 1)
        except PlaceSearchError:
            raise
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise PlaceSearchError("network") from exc
        if not content or len(content) > MAX_THUMBNAIL_BYTES:
            raise PlaceSearchError("image_size")
        return content

    def _request_json(
        self, route: str, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        query = urllib.parse.urlencode(parameters)
        request = urllib.request.Request(f"{self.base_url}{route}?{query}")
        request.add_header("Accept", "application/json")
        request.add_header("X-Subscription-Token", self.api_key)
        request.add_header("User-Agent", USER_AGENT)
        try:
            with self.opener(request, timeout=self.timeout) as response:
                payload = json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code in {401, 403}:
                code = "unauthorized"
            elif exc.code == 429:
                code = "rate_limit"
            elif exc.code in {400, 404, 422}:
                code = "request"
            else:
                code = "service"
            raise PlaceSearchError(code) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise PlaceSearchError("network") from exc
        except (ValueError, TypeError) as exc:
            raise PlaceSearchError("response") from exc
        if not isinstance(payload, dict):
            raise PlaceSearchError("response")
        return payload


def build_place_query(candidate: Candidate, language: str) -> str:
    if language == "en":
        values = [
            candidate.reverse_label,
            candidate.name,
            candidate.region,
            candidate.country,
        ]
    else:
        values = [
            candidate.name,
            candidate.region,
            candidate.country,
            candidate.reverse_label,
        ]
    parts: List[str] = []
    for value in values:
        normalized = " ".join(str(value or "").split())
        if normalized and normalized.casefold() not in {
            item.casefold() for item in parts
        }:
            parts.append(normalized)
    if not parts:
        parts = [f"{candidate.latitude:.5f},{candidate.longitude:.5f}"]
    query = " ".join(parts)
    words = query.split()
    query = " ".join(words[:50])
    return query[:400].strip()


def _image_query(query: str, language: str) -> str:
    suffix = (
        "tourist attractions cityscape landscape photos "
        "-food -restaurant -bottle -liquor -toy -shop"
        if language == "en"
        else "旅游景点 城市景观 风景照片 "
        "-美食 -餐厅 -白酒 -酒瓶 -模型 -拼图 -商品 -购物"
    )
    words = f"{query} {suffix}".split()
    return " ".join(words[:50])[:400].strip()


def parse_web_results(payload: Dict[str, Any]) -> List[PlaceWebResult]:
    web = payload.get("web")
    raw = web.get("results") if isinstance(web, dict) else []
    results: List[PlaceWebResult] = []
    seen = set()
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        url = _safe_https_url(item.get("url"))
        if not url or url in seen:
            continue
        title = _clean_text(item.get("title"), 220)
        if not title:
            continue
        profile = item.get("profile")
        source = (
            _clean_text(profile.get("long_name"), 120)
            if isinstance(profile, dict)
            else ""
        )
        source = source or urllib.parse.urlparse(url).hostname or ""
        results.append(
            PlaceWebResult(
                title=title,
                url=url,
                description=_clean_text(item.get("description"), 600),
                source=source,
            )
        )
        seen.add(url)
        if len(results) >= BRAVE_WEB_RESULT_LIMIT:
            break
    return results


def parse_image_results(payload: Dict[str, Any]) -> List[PlaceImageResult]:
    raw = payload.get("results")
    results: List[PlaceImageResult] = []
    seen = set()
    page_counts: Dict[str, int] = {}
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        thumbnail = item.get("thumbnail")
        properties = item.get("properties")
        thumbnail_url = _safe_brave_thumbnail(
            thumbnail.get("src") if isinstance(thumbnail, dict) else ""
        )
        page_url = _safe_https_url(item.get("url"))
        original_url = _safe_https_url(
            properties.get("url") if isinstance(properties, dict) else ""
        )
        identity = original_url or thumbnail_url
        if not thumbnail_url or not page_url or identity in seen:
            continue
        if page_counts.get(page_url, 0) >= BRAVE_IMAGE_PER_PAGE_LIMIT:
            continue
        title = _clean_text(item.get("title"), 180)
        source = (
            _clean_text(item.get("source"), 120)
            or urllib.parse.urlparse(page_url).hostname
            or ""
        )
        if _looks_like_non_place_image(title, page_url, source):
            continue
        width = _safe_int(
            properties.get("width") if isinstance(properties, dict) else 0
        )
        height = _safe_int(
            properties.get("height") if isinstance(properties, dict) else 0
        )
        results.append(
            PlaceImageResult(
                title=title or source,
                page_url=page_url,
                thumbnail_url=thumbnail_url,
                original_url=original_url,
                source=source,
                width=width,
                height=height,
            )
        )
        seen.add(identity)
        page_counts[page_url] = page_counts.get(page_url, 0) + 1
        if len(results) >= BRAVE_IMAGE_RESULT_LIMIT:
            break
    return results


def has_named_gis_identity(candidate: Candidate) -> bool:
    """Require a named, positively verified GIS identity before enrichment."""

    name = " ".join(str(candidate.name or "").split()).casefold()
    reverse_label = " ".join(
        str(candidate.reverse_label or "").split()
    )
    placeholder_names = {
        "",
        "candidate",
        "unknown",
        "unnamed",
        "unnamed place",
        "候选",
        "未知",
        "未命名",
        "未命名地点",
    }
    if (
        name in placeholder_names
        or not reverse_label
        or not candidate.gis_verified
    ):
        return False
    return any(
        check.matched is True
        and bool(str(check.detail or check.label or "").strip())
        and "unavailable" not in str(check.source or "").casefold()
        for check in candidate.gis_checks
    )


def has_online_place_material(details: PlaceDetails) -> bool:
    """Return whether Brave found anything useful enough to show."""

    return bool(details.web_results or details.images)


def _looks_like_non_place_image(
    title: str, page_url: str, source: str
) -> bool:
    parsed = urllib.parse.urlparse(page_url)
    host = (parsed.hostname or "").casefold()
    if any(marker in host for marker in _NON_PLACE_IMAGE_HOST_MARKERS):
        return True
    text = f" {title} {source} {parsed.path} ".casefold()
    return any(marker in text for marker in _NON_PLACE_IMAGE_TEXT_MARKERS)


def _country_parameter(value: str) -> str:
    country = str(value or "").upper()
    return country if re.fullmatch(r"[A-Z]{2}", country) else "ALL"


def _clean_text(value: Any, maximum: int) -> str:
    text = re.sub(r"<[^>]+>", " ", str(value or ""))
    text = " ".join(html.unescape(text).split())
    return text[:maximum].strip()


def _safe_https_url(value: Any) -> str:
    url = str(value or "").strip()
    parsed = urllib.parse.urlparse(url)
    return url if parsed.scheme == "https" and parsed.hostname else ""


def _safe_brave_thumbnail(value: Any) -> str:
    url = _safe_https_url(value)
    parsed = urllib.parse.urlparse(url)
    return url if parsed.hostname == "imgs.search.brave.com" else ""


def _safe_int(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0
