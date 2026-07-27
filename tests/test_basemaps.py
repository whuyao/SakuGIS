import unittest

from sakugis.basemaps import (
    GOOGLE_SATELLITE,
    GOOGLE_SATELLITE_FALLBACK,
    GOOGLE_SATELLITE_FALLBACK_SOURCE_URL,
    GOOGLE_SATELLITE_SOURCE_URL,
    OSM,
)


class BasemapDefinitionTests(unittest.TestCase):
    def test_osm_uses_official_https_endpoint(self):
        self.assertIn("https://tile.openstreetmap.org/{z}/{x}/{y}.png", OSM.uri)

    def test_osm_has_attribution(self):
        self.assertIn("OpenStreetMap contributors", OSM.attribution_html)

    def test_osm_zoom_is_bounded(self):
        self.assertIn("zmin=0", OSM.uri)
        self.assertIn("zmax=19", OSM.uri)

    def test_google_satellite_uses_requested_custom_xyz_source(self):
        self.assertEqual(
            GOOGLE_SATELLITE_SOURCE_URL,
            "http://mt2.google.cn/vt/lyrs=s&hl=zh-hk&g0=hk"
            "&x={x}&y={y}&z={z}",
        )
        self.assertIn("mt2.google.cn", GOOGLE_SATELLITE.uri)
        self.assertIn("%26x%3D{x}", GOOGLE_SATELLITE.uri)
        self.assertIn("Google Maps", GOOGLE_SATELLITE.attribution_html)
        self.assertTrue(
            GOOGLE_SATELLITE_FALLBACK_SOURCE_URL.startswith(
                "https://mt2.google.com/"
            )
        )
        self.assertIn("https://mt2.google.com", GOOGLE_SATELLITE_FALLBACK.uri)


if __name__ == "__main__":
    unittest.main()
