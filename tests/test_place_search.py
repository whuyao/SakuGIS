from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from sakugis.agent_models import Candidate
from sakugis.credentials import get_brave_api_key
from sakugis.i18n import set_language, tr
from sakugis.place_search import (
    BraveSearchClient,
    MemoryPlaceCache,
    PlaceSearchError,
    build_place_query,
    parse_image_results,
    parse_web_results,
)


def sample_candidate(**overrides) -> Candidate:
    values = {
        "candidate_id": "C1",
        "name": "黄鹤楼",
        "country": "中国",
        "region": "湖北省武汉市",
        "latitude": 30.5445,
        "longitude": 114.3046,
        "initial_score": 0.8,
        "ranking_score": 0.82,
        "radius_km": 8.0,
        "country_code": "CN",
        "gis_score": 0.76,
        "gis_coverage": 0.9,
        "reverse_label": "Yellow Crane Tower, Wuhan, China",
        "rationale": "Landmark evidence matches.",
    }
    values.update(overrides)
    return Candidate(**values)


class FakeSearchClient(BraveSearchClient):
    def __init__(self, payloads, errors=None, cache=None):
        super().__init__(api_key="test", cache=cache)
        self.payloads = payloads
        self.errors = errors or {}
        self.calls = []

    def _request_json(self, route, parameters):
        self.calls.append((route, dict(parameters)))
        if route in self.errors:
            raise PlaceSearchError(self.errors[route])
        return self.payloads.get(route, {})


class PlaceSearchTests(unittest.TestCase):
    def test_query_is_bounded_and_prefers_selected_language(self):
        candidate = sample_candidate(
            name="武汉 " * 80,
            reverse_label="Yellow Crane Tower Wuhan",
        )
        chinese = build_place_query(candidate, "zh_CN")
        english = build_place_query(candidate, "en")
        self.assertLessEqual(len(chinese), 400)
        self.assertLessEqual(len(chinese.split()), 50)
        self.assertTrue(chinese.startswith("武汉"))
        self.assertTrue(english.startswith("Yellow Crane Tower"))

    def test_web_results_are_clean_https_and_deduplicated(self):
        results = parse_web_results(
            {
                "web": {
                    "results": [
                        {
                            "title": "<b>Yellow &amp; Crane</b>",
                            "url": "https://example.com/place",
                            "description": "<p>Historic tower</p>",
                            "profile": {"long_name": "Example"},
                        },
                        {
                            "title": "Duplicate",
                            "url": "https://example.com/place",
                        },
                        {
                            "title": "Unsafe",
                            "url": "http://example.com/unsafe",
                        },
                    ]
                }
            }
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "Yellow & Crane")
        self.assertEqual(results[0].description, "Historic tower")

    def test_images_require_brave_proxy_and_source_page(self):
        results = parse_image_results(
            {
                "results": [
                    {
                        "title": "Tower",
                        "url": "https://source.example/tower",
                        "thumbnail": {
                            "src": "https://imgs.search.brave.com/a.jpg"
                        },
                        "properties": {
                            "url": "https://images.example/a.jpg",
                            "width": 800,
                            "height": 600,
                        },
                    },
                    {
                        "title": "Untrusted thumbnail",
                        "url": "https://source.example/b",
                        "thumbnail": {
                            "src": "https://images.example/b.jpg"
                        },
                    },
                ]
            }
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].width, 800)

    def test_search_returns_partial_results_and_uses_session_cache(self):
        cache = MemoryPlaceCache()
        client = FakeSearchClient(
            {
                "/web/search": {
                    "web": {
                        "results": [
                            {
                                "title": "Wuhan landmark",
                                "url": "https://example.com/wuhan",
                                "description": "A landmark in Wuhan.",
                            }
                        ]
                    }
                }
            },
            errors={"/images/search": "service"},
            cache=cache,
        )
        first = client.search_place(sample_candidate(), "en")
        second = client.search_place(sample_candidate(), "en")
        self.assertEqual(len(first.web_results), 1)
        self.assertEqual(first.warnings, ["service"])
        self.assertIs(first, second)
        self.assertEqual(len(client.calls), 2)

    def test_request_parameter_fallback_becomes_global(self):
        class FallbackClient(FakeSearchClient):
            def _request_json(self, route, parameters):
                self.calls.append((route, dict(parameters)))
                if len(self.calls) < 3:
                    raise PlaceSearchError("request")
                return {"ok": True}

        client = FallbackClient({})
        result = client._request_json_with_fallback(
            "/images/search",
            {"q": "test", "country": "ZZ", "search_lang": "en"},
        )
        self.assertEqual(result, {"ok": True})
        self.assertEqual(client.calls[1][1]["country"], "ALL")
        self.assertNotIn("search_lang", client.calls[2][1])

    def test_thumbnail_rejects_non_brave_host_before_network(self):
        client = BraveSearchClient(api_key="test")
        with self.assertRaises(PlaceSearchError) as context:
            client.fetch_thumbnail("https://example.com/photo.jpg")
        self.assertEqual(context.exception.code, "image_url")

    def test_brave_key_can_come_from_environment(self):
        with patch.dict(
            os.environ,
            {"SAKUGIS_BRAVE_API_KEY": "local-test-key"},
            clear=False,
        ):
            self.assertEqual(get_brave_api_key(), "local-test-key")

    def test_place_details_labels_exist_in_both_languages(self):
        keys = (
            "dock.place_details",
            "action.place_details",
            "place.empty_hint",
            "place.overview",
            "place.photos",
            "place.sources",
            "place.refresh",
            "place.source_note",
            "place.error.network",
        )
        try:
            for language in ("zh_CN", "en"):
                set_language(language)
                for key in keys:
                    self.assertNotEqual(tr(key), key)
        finally:
            set_language("zh_CN")


if __name__ == "__main__":
    unittest.main()
