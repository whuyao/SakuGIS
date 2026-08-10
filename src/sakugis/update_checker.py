"""GitHub Release update checks for SakuGIS."""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any, Callable, Iterable, Optional
import urllib.error
import urllib.request


RELEASES_API_URL = (
    "https://api.github.com/repos/whuyao/SakuGIS/releases?per_page=20"
)
VERSION_PATTERN = re.compile(
    r"^v?(\d+)\.(\d+)\.(\d+)(?:[-+][0-9A-Za-z.-]+)?$"
)


class UpdateCheckError(RuntimeError):
    """Raised when release metadata cannot be retrieved or interpreted."""


@dataclass(frozen=True)
class UpdateStatus:
    current_version: str
    latest_version: str
    release_name: str
    release_url: str
    download_url: str

    @property
    def update_available(self) -> bool:
        return version_tuple(self.latest_version) > version_tuple(
            self.current_version
        )


def version_tuple(version: str) -> tuple[int, int, int]:
    match = VERSION_PATTERN.fullmatch(version.strip())
    if not match:
        raise ValueError(f"Invalid semantic version: {version}")
    return tuple(int(part) for part in match.groups())


def parse_release_payload(
    payload: Any, current_version: str
) -> UpdateStatus:
    if not isinstance(payload, list):
        raise UpdateCheckError("GitHub release data is not a list.")

    releases = []
    for release in payload:
        if not isinstance(release, dict) or release.get("draft"):
            continue
        tag_name = str(release.get("tag_name") or "").strip()
        try:
            parsed_version = version_tuple(tag_name)
        except ValueError:
            continue
        releases.append((parsed_version, release))

    if not releases:
        raise UpdateCheckError("No published SakuGIS release was found.")

    _, latest = max(releases, key=lambda item: item[0])
    latest_version = str(latest["tag_name"]).strip().lstrip("v")
    release_url = _safe_github_url(latest.get("html_url"))
    download_url = _release_download_url(
        latest.get("assets"), latest_version
    )
    return UpdateStatus(
        current_version=current_version,
        latest_version=latest_version,
        release_name=str(latest.get("name") or f"SakuGIS {latest_version}"),
        release_url=release_url,
        download_url=download_url,
    )


def fetch_update_status(
    current_version: str,
    timeout: int = 8,
    opener: Optional[Callable[..., Any]] = None,
) -> UpdateStatus:
    request = urllib.request.Request(RELEASES_API_URL)
    request.add_header("Accept", "application/vnd.github+json")
    request.add_header(
        "User-Agent", f"SakuGIS/{current_version} (+https://urbancomp.net)"
    )
    request.add_header("X-GitHub-Api-Version", "2022-11-28")
    try:
        with (opener or urllib.request.urlopen)(
            request, timeout=timeout
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (
        urllib.error.HTTPError,
        urllib.error.URLError,
        TimeoutError,
        OSError,
        UnicodeError,
        json.JSONDecodeError,
    ) as exc:
        raise UpdateCheckError("Cannot read GitHub release information.") from exc
    return parse_release_payload(payload, current_version)


def _release_download_url(assets: Any, version: str) -> str:
    if not isinstance(assets, Iterable) or isinstance(assets, (str, bytes)):
        return ""
    expected_name = f"SakuGIS-{version}-Apple-Silicon.dmg"
    fallback = ""
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        name = str(asset.get("name") or "")
        url = _safe_github_url(asset.get("browser_download_url"))
        if not url:
            continue
        if name == expected_name:
            return url
        if name.casefold().endswith(".dmg") and not fallback:
            fallback = url
    return fallback


def _safe_github_url(value: Any) -> str:
    url = str(value or "").strip()
    if url.startswith("https://github.com/"):
        return url
    return ""
