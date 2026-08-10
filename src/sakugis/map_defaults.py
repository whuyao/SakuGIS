"""Startup map locations shared by the UI and tests."""

from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Optional, Sequence


@dataclass(frozen=True)
class StartupCity:
    """A major-city map view in WGS 84 coordinates."""

    key: str
    name_zh: str
    name_en: str
    longitude: float
    latitude: float
    longitude_span: float = 1.35
    latitude_span: float = 1.10

    @property
    def extent_wgs84(self) -> tuple[float, float, float, float]:
        half_width = self.longitude_span / 2.0
        half_height = self.latitude_span / 2.0
        return (
            self.longitude - half_width,
            self.latitude - half_height,
            self.longitude + half_width,
            self.latitude + half_height,
        )


STARTUP_CITIES: tuple[StartupCity, ...] = (
    StartupCity("wuhan", "武汉", "Wuhan", 114.3055, 30.5928),
    StartupCity("beijing", "北京", "Beijing", 116.4074, 39.9042),
    StartupCity("shanghai", "上海", "Shanghai", 121.4737, 31.2304),
    StartupCity("hong-kong", "香港", "Hong Kong", 114.1694, 22.3193),
    StartupCity("tokyo", "东京", "Tokyo", 139.6917, 35.6895),
    StartupCity("seoul", "首尔", "Seoul", 126.9780, 37.5665),
    StartupCity("singapore", "新加坡", "Singapore", 103.8198, 1.3521),
    StartupCity("mumbai", "孟买", "Mumbai", 72.8777, 19.0760),
    StartupCity("dubai", "迪拜", "Dubai", 55.2708, 25.2048),
    StartupCity("istanbul", "伊斯坦布尔", "Istanbul", 28.9784, 41.0082),
    StartupCity("london", "伦敦", "London", -0.1276, 51.5072),
    StartupCity("paris", "巴黎", "Paris", 2.3522, 48.8566),
    StartupCity("cairo", "开罗", "Cairo", 31.2357, 30.0444),
    StartupCity("lagos", "拉各斯", "Lagos", 3.3792, 6.5244),
    StartupCity("nairobi", "内罗毕", "Nairobi", 36.8219, -1.2921),
    StartupCity(
        "johannesburg",
        "约翰内斯堡",
        "Johannesburg",
        28.0473,
        -26.2041,
    ),
    StartupCity("new-york", "纽约", "New York", -74.0060, 40.7128),
    StartupCity("los-angeles", "洛杉矶", "Los Angeles", -118.2437, 34.0522),
    StartupCity("toronto", "多伦多", "Toronto", -79.3832, 43.6532),
    StartupCity("mexico-city", "墨西哥城", "Mexico City", -99.1332, 19.4326),
    StartupCity("sao-paulo", "圣保罗", "Sao Paulo", -46.6333, -23.5505),
    StartupCity(
        "buenos-aires",
        "布宜诺斯艾利斯",
        "Buenos Aires",
        -58.3816,
        -34.6037,
    ),
    StartupCity("sydney", "悉尼", "Sydney", 151.2093, -33.8688),
    StartupCity("melbourne", "墨尔本", "Melbourne", 144.9631, -37.8136),
)


def choose_startup_city(
    requested_key: str = "",
    cities: Sequence[StartupCity] = STARTUP_CITIES,
    chooser: Optional[random.Random] = None,
) -> StartupCity:
    """Choose one startup city, with an optional deterministic override."""

    normalized_key = requested_key.strip().casefold()
    if normalized_key:
        for city in cities:
            if city.key.casefold() == normalized_key:
                return city
    if not cities:
        raise ValueError("At least one startup city is required.")
    return (chooser or random.SystemRandom()).choice(tuple(cities))
