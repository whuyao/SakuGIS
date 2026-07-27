"""Policy-aware OSM reverse geocoding and feature verification."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from sakugis.agent_models import Candidate
from sakugis.gis_models import GISCheck, ReversePlace, SpatialConstraint


USER_AGENT = "SakuGIS/0.2.2 (+https://urbancomp.net)"
DEFAULT_NOMINATIM_URL = "https://nominatim.openstreetmap.org"
DEFAULT_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
_TAG_PATTERN = re.compile(r"^[a-zA-Z0-9_:.-]+$")
_nominatim_lock = threading.Lock()
_last_nominatim_request = 0.0
_overpass_lock = threading.Lock()
_last_overpass_request = 0.0

LEFT_DRIVING_COUNTRY_CODES = {
    "ag",
    "ai",
    "au",
    "bb",
    "bd",
    "bm",
    "bn",
    "bs",
    "bt",
    "bw",
    "cc",
    "ck",
    "cx",
    "cy",
    "dm",
    "fj",
    "fk",
    "gb",
    "gd",
    "gg",
    "gy",
    "hk",
    "id",
    "ie",
    "im",
    "in",
    "je",
    "jm",
    "jp",
    "ke",
    "ki",
    "kn",
    "ky",
    "lc",
    "lk",
    "ls",
    "mo",
    "ms",
    "mt",
    "mu",
    "mv",
    "mw",
    "my",
    "mz",
    "na",
    "nf",
    "np",
    "nr",
    "nu",
    "nz",
    "pg",
    "pk",
    "pn",
    "sb",
    "sc",
    "sg",
    "sh",
    "sr",
    "sz",
    "tc",
    "th",
    "tk",
    "tl",
    "to",
    "tt",
    "tv",
    "tz",
    "ug",
    "vc",
    "vg",
    "vi",
    "ws",
    "za",
    "zm",
    "zw",
}


class OSMServiceError(RuntimeError):
    pass


class JsonDiskCache:
    def __init__(self, root: Optional[Path] = None):
        configured = os.environ.get("SAKUGIS_OSM_CACHE_DIR")
        self.root = root or (
            Path(configured)
            if configured
            else Path.home() / "Library" / "Caches" / "SakuGIS" / "osm"
        )

    def get(self, namespace: str, key: str, ttl_seconds: int) -> Optional[Any]:
        path = self._path(namespace, key)
        try:
            if time.time() - path.stat().st_mtime > ttl_seconds:
                return None
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def set(self, namespace: str, key: str, value: Any) -> None:
        path = self._path(namespace, key)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(".tmp")
            temporary.write_text(
                json.dumps(value, ensure_ascii=False, separators=(",", ":")),
                encoding="utf-8",
            )
            os.replace(temporary, path)
        except OSError:
            return

    def _path(self, namespace: str, key: str) -> Path:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return self.root / namespace / f"{digest}.json"


class OSMServices:
    def __init__(
        self,
        nominatim_url: Optional[str] = None,
        overpass_url: Optional[str] = None,
        cache: Optional[JsonDiskCache] = None,
        timeout: int = 35,
    ):
        self.nominatim_url = (
            nominatim_url
            or os.environ.get("SAKUGIS_NOMINATIM_URL")
            or DEFAULT_NOMINATIM_URL
        ).rstrip("/")
        self.overpass_url = (
            overpass_url
            or os.environ.get("SAKUGIS_OVERPASS_URL")
            or DEFAULT_OVERPASS_URL
        )
        self.cache = cache or JsonDiskCache()
        self.timeout = timeout

    def reverse(
        self, latitude: float, longitude: float, language: str = "en,zh-CN"
    ) -> ReversePlace:
        rounded_key = f"v2:{latitude:.5f},{longitude:.5f},{language}"
        cached = self.cache.get("reverse", rounded_key, 30 * 24 * 60 * 60)
        if isinstance(cached, dict):
            return self._reverse_place(cached)

        query = urllib.parse.urlencode(
            {
                "format": "jsonv2",
                "lat": f"{latitude:.7f}",
                "lon": f"{longitude:.7f}",
                "zoom": "10",
                "addressdetails": "1",
                "namedetails": "1",
                "accept-language": language,
                "layer": "address",
            }
        )
        request = urllib.request.Request(f"{self.nominatim_url}/reverse?{query}")
        request.add_header("User-Agent", USER_AGENT)
        request.add_header("Accept", "application/json")
        payload = self._open_json(request, rate_limited=True)
        sanitized = {
            "display_name": payload.get("display_name", ""),
            "address": payload.get("address", {}),
            "namedetails": payload.get("namedetails", {}),
        }
        self.cache.set("reverse", rounded_key, sanitized)
        return self._reverse_place(sanitized)

    def overpass_checks(
        self,
        candidates: Sequence[Candidate],
        constraints: Sequence[SpatialConstraint],
    ) -> Dict[str, List[GISCheck]]:
        tag_constraints = [
            item
            for item in constraints
            if item.kind == "osm_tag"
            and _TAG_PATTERN.match(item.tag_key)
            and _TAG_PATTERN.match(item.tag_value)
        ]
        checks: Dict[str, List[GISCheck]] = {
            candidate.candidate_id: [] for candidate in candidates
        }
        if not tag_constraints:
            return checks

        for constraint in tag_constraints:
            query = self._overpass_query(candidates, [constraint])
            cached = self.cache.get("overpass", query, 7 * 24 * 60 * 60)
            if isinstance(cached, dict):
                payload = cached
            else:
                body = urllib.parse.urlencode({"data": query}).encode("utf-8")
                request = urllib.request.Request(
                    self.overpass_url, data=body, method="POST"
                )
                request.add_header("User-Agent", USER_AGENT)
                request.add_header(
                    "Content-Type",
                    "application/x-www-form-urlencoded; charset=utf-8",
                )
                try:
                    self._wait_for_overpass_slot()
                    payload = self._open_json(request)
                except OSMServiceError:
                    for candidate in candidates:
                        checks[candidate.candidate_id].append(
                            GISCheck(
                                check_id=constraint.constraint_id,
                                kind="spatial_constraint",
                                label=constraint.label,
                                matched=None,
                                source="OSM Overpass unavailable",
                                weight=constraint.importance,
                                required=constraint.required,
                            )
                        )
                    continue
                self.cache.set("overpass", query, payload)

            features = self._features(payload.get("elements", []))
            for candidate in candidates:
                matching = [
                    feature
                    for feature in features
                    if feature[1].get(constraint.tag_key) == constraint.tag_value
                ]
                distances = [
                    (
                        _distance_to_feature_km(
                            candidate.latitude,
                            candidate.longitude,
                            feature[0],
                        ),
                        feature,
                    )
                    for feature in matching
                ]
                distances.sort(key=lambda item: item[0])
                local_distances = [
                    item
                    for item in distances
                    if item[0] <= constraint.radius_km * 1.6
                ]
                nearby = [
                    item
                    for item in local_distances
                    if item[0] <= constraint.radius_km
                ]
                sample_names = [
                    str(item[1][1].get("name") or item[1][1].get("name:en") or "")
                    for item in nearby[:3]
                ]
                sample_names = [name for name in sample_names if name]
                checks[candidate.candidate_id].append(
                    GISCheck(
                        check_id=constraint.constraint_id,
                        kind="spatial_constraint",
                        label=constraint.label,
                        matched=bool(nearby),
                        source="OSM Overpass",
                        count=len(nearby),
                        nearest_distance_km=(
                            round(local_distances[0][0], 2)
                            if local_distances
                            else None
                        ),
                        detail=", ".join(sample_names),
                        strength=(
                            max(
                                0.60,
                                1.0
                                - 0.40
                                * nearby[0][0]
                                / max(0.1, constraint.radius_km),
                            )
                            if nearby
                            else 0.25
                        ),
                        weight=constraint.importance,
                        required=constraint.required,
                    )
                )
        return checks

    @staticmethod
    def driving_side_check(
        candidate_id: str,
        country_code: str,
        weight: float = 1.0,
        required: bool = False,
    ) -> GISCheck:
        normalized = country_code.casefold()
        matched = normalized in LEFT_DRIVING_COUNTRY_CODES if normalized else None
        return GISCheck(
            check_id="left_hand_traffic",
            kind="country_rule",
            label="left-hand traffic",
            matched=matched,
            source="country driving-side rule",
            detail=normalized.upper(),
            strength=(
                1.0
                if matched is True
                else 0.0 if matched is False else None
            ),
            weight=weight,
            required=required,
        )

    @staticmethod
    def _overpass_query(
        candidates: Sequence[Candidate],
        constraints: Sequence[SpatialConstraint],
    ) -> str:
        clauses = []
        for candidate in candidates:
            for constraint in constraints:
                for south, west, north, east in OSMServices._bounding_boxes(
                    candidate.latitude,
                    candidate.longitude,
                    constraint.radius_km,
                ):
                    clauses.append(
                        'nwr["{key}"="{value}"]'
                        "({south:.6f},{west:.6f},{north:.6f},{east:.6f});".format(
                            key=constraint.tag_key,
                            value=constraint.tag_value,
                            south=south,
                            west=west,
                            north=north,
                            east=east,
                        )
                    )
        return "[out:json][timeout:30];(" + "".join(clauses) + ");out geom 2000;"

    @staticmethod
    def _bounding_boxes(
        latitude: float, longitude: float, radius_km: float
    ) -> List[Tuple[float, float, float, float]]:
        bounded_radius = max(1.0, min(100.0, radius_km))
        latitude_delta = bounded_radius / 111.0
        longitude_scale = max(
            0.1, math.cos(math.radians(latitude))
        )
        longitude_delta = bounded_radius / (111.0 * longitude_scale)
        south = max(-90.0, latitude - latitude_delta)
        north = min(90.0, latitude + latitude_delta)
        west = longitude - longitude_delta
        east = longitude + longitude_delta
        if west < -180.0:
            return [
                (south, west + 360.0, north, 180.0),
                (south, -180.0, north, east),
            ]
        if east > 180.0:
            return [
                (south, west, north, 180.0),
                (south, -180.0, north, east - 360.0),
            ]
        return [(south, west, north, east)]

    @staticmethod
    def _features(
        elements: Iterable[Any],
    ) -> List[Tuple[List[Tuple[float, float]], Dict[str, Any]]]:
        features = []
        for element in elements:
            if not isinstance(element, dict):
                continue
            points: List[Tuple[float, float]] = []
            geometry = element.get("geometry")
            if isinstance(geometry, list):
                for point in geometry:
                    if not isinstance(point, dict):
                        continue
                    try:
                        points.append((float(point["lat"]), float(point["lon"])))
                    except (KeyError, TypeError, ValueError):
                        continue
            if not points:
                center = (
                    element.get("center")
                    if isinstance(element.get("center"), dict)
                    else {}
                )
                latitude = element.get("lat", center.get("lat"))
                longitude = element.get("lon", center.get("lon"))
                try:
                    points.append((float(latitude), float(longitude)))
                except (TypeError, ValueError):
                    continue
            tags = element.get("tags")
            features.append((points, tags if isinstance(tags, dict) else {}))
        return features

    @staticmethod
    def _reverse_place(payload: Dict[str, Any]) -> ReversePlace:
        address = payload.get("address")
        address = address if isinstance(address, dict) else {}
        locality = next(
            (
                str(address[key])
                for key in ("city", "town", "village", "municipality", "county")
                if address.get(key)
            ),
            "",
        )
        region = next(
            (
                str(address[key])
                for key in ("state", "region", "state_district", "county")
                if address.get(key)
            ),
            "",
        )
        return ReversePlace(
            display_name=str(payload.get("display_name") or ""),
            country=str(address.get("country") or ""),
            country_code=str(address.get("country_code") or "").upper(),
            region=region,
            locality=locality,
            source="OSM Nominatim",
            aliases=[
                str(value)
                for value in (
                    payload.get("namedetails", {}).values()
                    if isinstance(payload.get("namedetails"), dict)
                    else []
                )
                if value
            ],
        )

    def _open_json(
        self, request: urllib.request.Request, rate_limited: bool = False
    ) -> Dict[str, Any]:
        if rate_limited:
            self._wait_for_nominatim_slot()
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.load(response)
        except urllib.error.HTTPError as exc:
            raise OSMServiceError(f"OSM HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise OSMServiceError("OSM service unavailable") from exc
        except (OSError, ValueError) as exc:
            raise OSMServiceError("Invalid OSM response") from exc
        if not isinstance(payload, dict):
            raise OSMServiceError("Invalid OSM response")
        return payload

    @staticmethod
    def _wait_for_nominatim_slot() -> None:
        global _last_nominatim_request
        with _nominatim_lock:
            elapsed = time.monotonic() - _last_nominatim_request
            if elapsed < 1.05:
                time.sleep(1.05 - elapsed)
            _last_nominatim_request = time.monotonic()

    @staticmethod
    def _wait_for_overpass_slot() -> None:
        global _last_overpass_request
        with _overpass_lock:
            elapsed = time.monotonic() - _last_overpass_request
            if elapsed < 1.5:
                time.sleep(1.5 - elapsed)
            _last_overpass_request = time.monotonic()


def _haversine_km(
    latitude_a: float,
    longitude_a: float,
    latitude_b: float,
    longitude_b: float,
) -> float:
    earth_radius_km = 6371.0088
    lat_a = math.radians(latitude_a)
    lat_b = math.radians(latitude_b)
    delta_lat = lat_b - lat_a
    delta_lon = math.radians(
        ((longitude_b - longitude_a + 180.0) % 360.0) - 180.0
    )
    value = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat_a) * math.cos(lat_b) * math.sin(delta_lon / 2) ** 2
    )
    return earth_radius_km * 2 * math.asin(min(1.0, math.sqrt(value)))


def _distance_to_feature_km(
    latitude: float,
    longitude: float,
    points: Sequence[Tuple[float, float]],
) -> float:
    if not points:
        return float("inf")
    if len(points) == 1:
        return _haversine_km(
            latitude, longitude, points[0][0], points[0][1]
        )
    earth_radius_km = 6371.0088
    latitude_radians = math.radians(latitude)

    def project(point: Tuple[float, float]) -> Tuple[float, float]:
        delta_longitude = (
            (point[1] - longitude + 180.0) % 360.0
        ) - 180.0
        return (
            earth_radius_km
            * math.radians(delta_longitude)
            * math.cos(latitude_radians),
            earth_radius_km * math.radians(point[0] - latitude),
        )

    projected = [project(point) for point in points]
    nearest = float("inf")
    for first, second in zip(projected, projected[1:]):
        delta_x = second[0] - first[0]
        delta_y = second[1] - first[1]
        length_squared = delta_x * delta_x + delta_y * delta_y
        if length_squared <= 1e-12:
            distance = math.hypot(first[0], first[1])
        else:
            fraction = max(
                0.0,
                min(
                    1.0,
                    -(first[0] * delta_x + first[1] * delta_y)
                    / length_squared,
                ),
            )
            distance = math.hypot(
                first[0] + fraction * delta_x,
                first[1] + fraction * delta_y,
            )
        nearest = min(nearest, distance)
    return nearest
