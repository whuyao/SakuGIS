"""Online basemap definitions.

Provider-specific definitions are isolated here so a deployment-specific XYZ
source can later be replaced by the official Google Maps Tile API adapter.
"""

from __future__ import annotations

from dataclasses import dataclass
import socket
from urllib.parse import quote


@dataclass(frozen=True)
class BasemapDefinition:
    key: str
    name: str
    provider: str
    uri: str
    attribution_html: str


OSM = BasemapDefinition(
    key="osm-standard",
    name="OpenStreetMap",
    provider="wms",
    uri=(
        "type=xyz"
        "&url=https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        "&zmin=0"
        "&zmax=19"
        "&crs=EPSG3857"
    ),
    attribution_html=(
        '© <a style="color:#55DDF8" '
        'href="https://www.openstreetmap.org/copyright">'
        "OpenStreetMap contributors</a>"
    ),
)


GOOGLE_SATELLITE_SOURCE_URL = (
    "http://mt2.google.cn/vt/lyrs=s&hl=zh-hk&g0=hk&x={x}&y={y}&z={z}"
)
def _xyz_uri(source_url: str, maximum_zoom: int = 20) -> str:
    return (
        "type=xyz"
        f"&url={quote(source_url, safe=':/{}')}"
        "&zmin=0"
        f"&zmax={maximum_zoom}"
        "&crs=EPSG3857"
    )


GOOGLE_SATELLITE = BasemapDefinition(
    key="google-satellite-custom-xyz",
    name="Google Satellite",
    provider="wms",
    uri=_xyz_uri(GOOGLE_SATELLITE_SOURCE_URL),
    attribution_html=(
        '© <a style="color:#55DDF8" '
        'href="https://www.google.com/maps">Google Maps</a>'
    ),
)

GOOGLE_SATELLITE_FALLBACK_SOURCE_URL = (
    "https://mt2.google.com/vt/lyrs=s&hl=zh-hk&gl=hk&x={x}&y={y}&z={z}"
)
GOOGLE_SATELLITE_FALLBACK = BasemapDefinition(
    key=GOOGLE_SATELLITE.key,
    name=GOOGLE_SATELLITE.name,
    provider=GOOGLE_SATELLITE.provider,
    uri=_xyz_uri(GOOGLE_SATELLITE_FALLBACK_SOURCE_URL),
    attribution_html=GOOGLE_SATELLITE.attribution_html,
)


def available_google_satellite() -> BasemapDefinition:
    """Prefer the requested .cn source and use HTTPS if it cannot resolve."""

    try:
        socket.getaddrinfo("mt2.google.cn", 80)
    except OSError:
        return GOOGLE_SATELLITE_FALLBACK
    return GOOGLE_SATELLITE
