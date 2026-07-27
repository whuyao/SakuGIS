import json
import re
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from sakugis.agent_models import Candidate, Evidence, RetrievedPlace
from sakugis.candidate_retrieval import HybridCandidateRetriever
from sakugis.credentials import load_profile_csv
from sakugis.geo_agents import GeoAgentPipeline
from sakugis.gis_models import CandidateGISResult, GISCheck, ReversePlace
from sakugis.gis_verifier import GISVerifier
from sakugis.i18n import set_language, tr
from sakugis.osm_services import OSMServices, _distance_to_feature_km
from sakugis.postgis_provider import PostGISConfig, PostGISError
from sakugis.prompt_budget import (
    CANDIDATE_PROMPT_CHAR_LIMIT,
    EVIDENCE_PROMPT_CHAR_LIMIT,
    VERIFY_PROMPT_CHAR_LIMIT,
)
from sakugis.qwen_client import (
    QwenApiError,
    QwenClient,
    _image_dimension_for_count,
    extract_json_object,
)
from sakugis.reporting import build_markdown_report
from sakugis.ranking import fuse_candidate_score, select_diverse_candidates
from sakugis.spatial_constraints import plan_spatial_constraints


class FakeQwenClient:
    model = "fake-qwen"

    def __init__(self):
        self.calls = []

    def chat_json(
        self,
        system_prompt,
        user_prompt,
        image_path="",
        image_paths=None,
        max_tokens=4096,
    ):
        self.calls.append(
            (
                system_prompt,
                user_prompt,
                image_path,
                list(image_paths or []),
                max_tokens,
            )
        )
        if "Agent 1" in system_prompt:
            photo_ids = re.findall(r'"photo_id":"(P\d+)"', user_prompt)
            return {
                "summary": "看见左侧通行和海岸",
                "evidence": [
                    {
                        "id": "E1",
                        "kind": "traffic",
                        "value": "左侧通行",
                        "reliability": 0.8,
                        "source": "user-query",
                        "scale": "country",
                        "photo_ids": photo_ids,
                    }
                ],
            }
        if "Agent 2" in system_prompt:
            return {
                "candidates": [
                    {
                        "id": "C1",
                        "name": "奥克兰",
                        "country": "新西兰",
                        "country_code": "NZ",
                        "region": "奥克兰",
                        "latitude": -36.8485,
                        "longitude": 174.7633,
                        "initial_score": 0.7,
                        "radius_km": 80,
                    },
                    {
                        "id": "BAD",
                        "name": "无效坐标",
                        "latitude": 200,
                        "longitude": 0,
                    },
                ]
            }
        support_id = "P1-E1" if "P1-E1" in user_prompt else "E1"
        return {
            "summary": "奥克兰最符合当前证据",
            "caveat": "尚未检查参考影像",
            "candidates": [
                {
                    "id": "C1",
                    "evidence_score": 0.9,
                    "radius_km": 50,
                    "supporting_evidence": [support_id],
                    "contradictions": [],
                    "rationale": "左侧通行且临海",
                }
            ],
        }


class RecordingQwenClient(QwenClient):
    def __init__(self, max_prompt_chars=48000):
        super().__init__(
            api_key="test-key",
            base_url="https://example.invalid",
            model="fake-qwen",
            max_prompt_chars=max_prompt_chars,
        )
        self.payloads = []

    def _post(self, route, payload):
        self.payloads.append((route, payload))
        return {"choices": [{"message": {"content": '{"ok":true}'}}]}


class RetryingQwenClient(RecordingQwenClient):
    def _post(self, route, payload):
        self.payloads.append((route, payload.copy()))
        if len(self.payloads) == 1:
            return {
                "choices": [
                    {"message": {"content": '{"items":["incomplete"'}}
                ]
            }
        return {"choices": [{"message": {"content": '{"ok":true}'}}]}


class FakeGISVerifier:
    def verify(self, candidates, constraints, progress=None):
        results = {}
        for candidate in candidates:
            candidate.gis_score = 0.8
            candidate.gis_coverage = 1.0
            candidate.gis_verified = True
            candidate.reverse_label = "Auckland, New Zealand"
            candidate.gis_backend = "fake-postgis"
            candidate.gis_checks = [
                GISCheck(
                    check_id="reverse_country",
                    kind="reverse_geocode",
                    label="country",
                    matched=True,
                    source="fake-postgis",
                )
            ]
            results[candidate.candidate_id] = CandidateGISResult(
                candidate_id=candidate.candidate_id,
                reverse=ReversePlace(
                    display_name=candidate.reverse_label,
                    country="New Zealand",
                    country_code="NZ",
                    source="fake-postgis",
                ),
                checks=candidate.gis_checks,
                gis_score=0.8,
                coverage=1.0,
                verified=True,
                backend="fake-postgis",
            )
        return results, "fake-postgis"


class FakeCandidateRetriever:
    def resolve(self, candidates, progress=None):
        resolved = list(candidates)
        for index, candidate in enumerate(resolved, 1):
            if progress:
                progress(index, len(resolved))
            candidate.retrieval_verified = True
            candidate.retrieval_source = "fake place index"
            candidate.retrieval_label = candidate.name
            candidate.retrieval_score = candidate.initial_score
        return resolved, "fake place index", len(resolved)


class FakePlaceOSM:
    def __init__(self, places, reverse_place=None):
        self.places = places
        self.reverse_place = reverse_place
        self.queries = []
        self.reverse_queries = []

    def search_places(self, query_text, language="en", limit=3):
        self.queries.append((query_text, language, limit))
        return list(self.places)

    def reverse_place_record(
        self, latitude, longitude, language="en,zh-CN"
    ):
        self.reverse_queries.append((latitude, longitude, language))
        return self.reverse_place


class DisabledPostGIS:
    enabled = False


class FakePlacePostGIS:
    enabled = True

    def __init__(self, places):
        self.places = places

    def search_places(self, query_text, limit=3):
        return list(self.places)


class AgentCoreTests(unittest.TestCase):
    def test_extracts_fenced_json(self):
        self.assertEqual(
            extract_json_object('```json\n{"answer": 42}\n```'),
            {"answer": 42},
        )

    def test_candidate_rejects_invalid_coordinates(self):
        with self.assertRaises(ValueError):
            Candidate.from_dict({"latitude": 91, "longitude": 0}, 0)

    def test_agent2_drops_ambiguous_non_place_candidates(self):
        candidates = GeoAgentPipeline._parse_candidates(
            {
                "candidates": [
                    {
                        "name": "箱根公园或附近寺庙",
                        "country": "日本",
                        "latitude": 35.2,
                        "longitude": 139.0,
                        "initial_score": 0.9,
                    },
                    {
                        "name": "新仓山浅间公园",
                        "country": "日本",
                        "latitude": 35.5,
                        "longitude": 138.8,
                        "initial_score": 0.8,
                    },
                ]
            }
        )

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].name, "新仓山浅间公园")

    def test_pipeline_runs_three_agents_and_marks_result_uncalibrated(self):
        client = FakeQwenClient()
        result = GeoAgentPipeline(
            client, FakeGISVerifier(), FakeCandidateRetriever()
        ).run(
            query="寻找左侧通行且临海的城市"
        )
        self.assertEqual(len(client.calls), 3)
        self.assertEqual(
            [call[4] for call in client.calls],
            [3072, 3072, 4096],
        )
        self.assertEqual(len(result.candidates), 1)
        self.assertEqual(result.candidates[0].name, "奥克兰")
        self.assertAlmostEqual(result.candidates[0].ranking_score, 0.7478)
        self.assertEqual(result.confidence_status, "uncalibrated")
        self.assertEqual(result.gis_backend, "fake-postgis")
        self.assertEqual(result.retrieval_backend, "fake place index")
        self.assertEqual(result.retrieval_resolved_count, 1)
        self.assertTrue(result.candidates[0].gis_verified)
        self.assertEqual(result.candidates[0].gis_coverage, 1.0)

        set_language("zh_CN")
        report = build_markdown_report(
            result,
            generated_at=datetime(2026, 7, 27, tzinfo=timezone.utc),
        )
        self.assertIn("# SakuGIS 全球位置查询报告", report)
        self.assertIn("奥克兰", report)
        self.assertIn("80.0/100", report)
        self.assertIn("GIS 查询约束", report)
        self.assertIn("评分分解", report)
        self.assertIn("收缩后证据复核", report)
        self.assertIn("不应解释为统计概率", report)

    def test_pipeline_jointly_scores_multiple_case_photos(self):
        client = FakeQwenClient()
        paths = ["/tmp/case-a.jpg", "/tmp/case-b.jpg"]
        result = GeoAgentPipeline(
            client, FakeGISVerifier(), FakeCandidateRetriever()
        ).run(
            image_paths=paths,
            query="这两张照片拍摄于同一地点",
        )
        candidate = result.candidates[0]
        self.assertEqual(result.image_paths, paths)
        self.assertEqual(result.image_path, paths[0])
        self.assertEqual(len(client.calls), 4)
        self.assertEqual(client.calls[0][3], [paths[0]])
        self.assertEqual(client.calls[1][3], [paths[1]])
        self.assertTrue(all(len(call[3]) <= 1 for call in client.calls))
        self.assertEqual(
            [call[4] for call in client.calls],
            [3072, 3072, 3072, 4096],
        )
        self.assertEqual(candidate.photo_support_count, 2)
        self.assertEqual(candidate.photo_total_count, 2)
        self.assertEqual(candidate.photo_consistency, 1.0)
        self.assertIn("跨照片覆盖", build_markdown_report(result))

    def test_real_place_retrieval_replaces_model_coordinates(self):
        candidate = Candidate.from_dict(
            {
                "id": "C1",
                "name": "新仓山浅间公园",
                "country": "日本",
                "country_code": "JP",
                "region": "富士吉田市",
                "latitude": 35.49,
                "longitude": 138.79,
                "initial_score": 0.82,
                "radius_km": 20,
                "search_query": "Arakurayama Sengen Park, Japan",
            },
            0,
        )
        wrong_country = RetrievedPlace(
            name="Sengen Park",
            display_name="Sengen Park, California, United States",
            country="United States",
            country_code="US",
            region="California",
            latitude=34.0,
            longitude=-118.0,
            source="OSM Nominatim",
            source_id="node/1",
            importance=0.8,
        )
        correct = RetrievedPlace(
            name="新仓山浅间公园",
            display_name="新仓山浅间公园, 富士吉田市, 山梨県, 日本",
            country="日本",
            country_code="JP",
            region="山梨県",
            latitude=35.5013,
            longitude=138.8014,
            source="OSM Nominatim",
            source_id="way/2",
            importance=0.7,
        )
        osm = FakePlaceOSM([wrong_country, correct])
        retriever = HybridCandidateRetriever(
            osm=osm,
            postgis=DisabledPostGIS(),
        )

        candidates, backend, resolved_count = retriever.resolve([candidate])

        self.assertEqual(resolved_count, 1)
        self.assertEqual(backend, "OSM Nominatim")
        self.assertAlmostEqual(candidates[0].latitude, 35.5013)
        self.assertAlmostEqual(candidates[0].longitude, 138.8014)
        self.assertTrue(candidates[0].retrieval_verified)
        self.assertEqual(candidates[0].retrieval_source_id, "way/2")
        self.assertIn("Arakurayama", osm.queries[0][0])

    def test_low_similarity_postgis_hit_falls_back_to_nominatim(self):
        candidate = Candidate.from_dict(
            {
                "name": "新仓山浅间公园",
                "country": "日本",
                "country_code": "JP",
                "region": "富士吉田市",
                "latitude": 35.49,
                "longitude": 138.79,
                "initial_score": 0.82,
                "radius_km": 20,
            },
            0,
        )
        wrong = RetrievedPlace(
            name="Sengen Park",
            display_name="Sengen Park, United States",
            country="United States",
            country_code="US",
            region="California",
            latitude=34.0,
            longitude=-118.0,
            source="PostGIS OSM index",
        )
        correct = RetrievedPlace(
            name="新倉山浅間公園",
            display_name="新倉山浅間公園, 山梨県, 日本",
            country="日本",
            country_code="JP",
            region="山梨県",
            latitude=35.50049,
            longitude=138.80082,
            source="OSM Nominatim",
        )
        retriever = HybridCandidateRetriever(
            osm=FakePlaceOSM([correct]),
            postgis=FakePlacePostGIS([wrong]),
        )

        candidates, backend, resolved_count = retriever.resolve([candidate])

        self.assertEqual(resolved_count, 1)
        self.assertIn("PostGIS OSM index", backend)
        self.assertIn("OSM Nominatim", backend)
        self.assertEqual(candidates[0].retrieval_source, "OSM Nominatim")
        self.assertAlmostEqual(candidates[0].latitude, 35.50049)

    def test_failed_alias_search_falls_back_to_reverse_place_record(self):
        candidate = Candidate.from_dict(
            {
                "name": "北外滩滨江绿地",
                "country": "中国",
                "country_code": "CN",
                "region": "上海市虹口区",
                "latitude": 31.2456,
                "longitude": 121.4985,
                "initial_score": 0.82,
                "radius_km": 20,
            },
            0,
        )
        reverse_place = RetrievedPlace(
            name="上海白玉兰广场",
            display_name="上海白玉兰广场, 虹口区, 上海市, 中国",
            country="中国",
            country_code="CN",
            region="上海市",
            latitude=31.24555,
            longitude=121.49861,
            source="OSM Nominatim reverse",
            source_id="way/1234",
            importance=0.62,
        )
        osm = FakePlaceOSM([], reverse_place=reverse_place)
        retriever = HybridCandidateRetriever(
            osm=osm,
            postgis=DisabledPostGIS(),
        )

        candidates, backend, resolved_count = retriever.resolve([candidate])

        self.assertEqual(resolved_count, 1)
        self.assertEqual(
            candidates[0].retrieval_source, "OSM Nominatim reverse"
        )
        self.assertEqual(candidates[0].retrieval_source_id, "way/1234")
        self.assertTrue(candidates[0].retrieval_verified)
        self.assertIn("OSM Nominatim reverse", backend)
        self.assertEqual(
            osm.reverse_queries[0][:2], (31.2456, 121.4985)
        )

    def test_far_same_country_text_hit_cannot_override_model_region(self):
        candidate = Candidate.from_dict(
            {
                "name": "北外滩滨江绿地",
                "country": "中国",
                "country_code": "CN",
                "region": "上海市虹口区",
                "latitude": 31.2456,
                "longitude": 121.4985,
                "initial_score": 0.82,
                "radius_km": 20,
            },
            0,
        )
        far_wrong = RetrievedPlace(
            name="东北农业大学",
            display_name="东北农业大学, 哈尔滨市, 黑龙江省, 中国",
            country="中国",
            country_code="CN",
            region="黑龙江省",
            latitude=45.742,
            longitude=126.727,
            source="OSM Nominatim",
            source_id="way/99",
            importance=0.66,
        )
        local_reverse = RetrievedPlace(
            name="上海白玉兰广场",
            display_name="上海白玉兰广场, 虹口区, 上海市, 中国",
            country="中国",
            country_code="CN",
            region="上海市",
            latitude=31.24555,
            longitude=121.49861,
            source="OSM Nominatim reverse",
            source_id="way/1234",
            importance=0.62,
        )
        osm = FakePlaceOSM([far_wrong], reverse_place=local_reverse)
        retriever = HybridCandidateRetriever(
            osm=osm,
            postgis=DisabledPostGIS(),
        )

        candidates, _, resolved_count = retriever.resolve([candidate])

        self.assertEqual(resolved_count, 1)
        self.assertEqual(
            candidates[0].retrieval_source, "OSM Nominatim reverse"
        )
        self.assertEqual(candidates[0].retrieval_source_id, "way/1234")

    def test_cross_photo_correlation_group_merges_different_wording(self):
        evidence = GeoAgentPipeline._parse_evidence(
            {
                "evidence": [
                    {
                        "id": "P1-E1",
                        "kind": "landmark",
                        "value": "红白相间的五层塔",
                        "reliability": 0.78,
                        "photo_ids": ["P1"],
                        "correlation_group": "five-storey-pagoda",
                    },
                    {
                        "id": "P2-E1",
                        "kind": "landmark",
                        "value": "山坡上的五重塔",
                        "reliability": 0.91,
                        "photo_ids": ["P2"],
                        "correlation_group": "five-storey-pagoda",
                    },
                ]
            },
            [],
        )

        self.assertEqual(len(evidence), 1)
        self.assertEqual(evidence[0].photo_ids, ["P1", "P2"])
        self.assertEqual(evidence[0].value, "山坡上的五重塔")
        self.assertAlmostEqual(evidence[0].reliability, 0.91)

    def test_nominatim_search_record_is_structured(self):
        place = OSMServices._search_place(
            {
                "lat": "35.5013",
                "lon": "138.8014",
                "display_name": "新仓山浅间公园, 富士吉田市, 日本",
                "namedetails": {"name": "新仓山浅间公园"},
                "address": {
                    "country": "日本",
                    "country_code": "jp",
                    "state": "山梨県",
                },
                "osm_type": "way",
                "osm_id": 123,
                "importance": 0.72,
            }
        )

        self.assertIsNotNone(place)
        self.assertEqual(place.country_code, "JP")
        self.assertEqual(place.region, "山梨県")
        self.assertEqual(place.source_id, "way/123")

    def test_nominatim_reverse_record_uses_real_source_identity(self):
        place = OSMServices._search_place(
            {
                "lat": "31.24555",
                "lon": "121.49861",
                "display_name": "上海白玉兰广场, 虹口区, 上海市, 中国",
                "namedetails": {"name": "上海白玉兰广场"},
                "address": {
                    "country": "中国",
                    "country_code": "cn",
                    "state": "上海市",
                },
                "osm_type": "way",
                "osm_id": 1234,
                "importance": 0.62,
            }
        )

        self.assertIsNotNone(place)
        self.assertEqual(place.source_id, "way/1234")
        self.assertAlmostEqual(place.latitude, 31.24555)

    def test_reverse_lookup_preserves_the_verified_query_coordinate(self):
        class MemoryCache:
            def get(self, namespace, key, ttl_seconds):
                return {
                    "lat": "64.2333478",
                    "lon": "-16.3826106",
                    "display_name": (
                        "Sveitarfélagið Hornafjörður, Iceland"
                    ),
                    "namedetails": {
                        "name": "Sveitarfélagið Hornafjörður"
                    },
                    "address": {
                        "country": "Iceland",
                        "country_code": "is",
                        "state": "Southern Region",
                    },
                    "osm_type": "relation",
                    "osm_id": 55966,
                }

            def set(self, namespace, key, value):
                raise AssertionError("cached test must not write")

        osm = OSMServices(cache=MemoryCache())

        place = osm.reverse_place_record(64.0784, -16.2306)

        self.assertIsNotNone(place)
        self.assertAlmostEqual(place.latitude, 64.0784)
        self.assertAlmostEqual(place.longitude, -16.2306)
        self.assertEqual(place.source_id, "relation/55966")
        self.assertEqual(place.source, "OSM Nominatim reverse")

    def test_qwen_requests_are_stateless_between_location_runs(self):
        client = RecordingQwenClient()
        client.chat_json("system", "FIRST_LOCATION_ONLY")
        client.chat_json("system", "SECOND_LOCATION_ONLY")

        self.assertEqual(len(client.payloads), 2)
        first = client.payloads[0][1]
        second = client.payloads[1][1]
        self.assertEqual(len(first["messages"]), 2)
        self.assertEqual(len(second["messages"]), 2)
        self.assertNotIn(
            "FIRST_LOCATION_ONLY",
            json.dumps(second, ensure_ascii=False),
        )
        self.assertEqual(client.last_request_stats["message_count"], 2)
        self.assertEqual(client.last_request_stats["image_count"], 0)

    def test_qwen_rejects_oversize_prompt_before_network_request(self):
        client = RecordingQwenClient(max_prompt_chars=128)
        with self.assertRaises(QwenApiError):
            client.chat_json("s" * 80, "u" * 80)
        self.assertEqual(client.payloads, [])

    def test_qwen_retries_incomplete_json_once_without_history(self):
        client = RetryingQwenClient()

        result = client.chat_json(
            "return JSON",
            "test input",
            max_tokens=3072,
        )

        self.assertEqual(result, {"ok": True})
        self.assertEqual(len(client.payloads), 2)
        retry_payload = client.payloads[1][1]
        self.assertEqual(len(retry_payload["messages"]), 2)
        self.assertEqual(retry_payload["temperature"], 0)
        self.assertEqual(retry_payload["max_tokens"], 4096)
        self.assertEqual(client.last_request_stats["retry_count"], 1)

    def test_multi_image_resize_policy_is_defensive(self):
        self.assertEqual(_image_dimension_for_count(1), 2048)
        self.assertEqual(_image_dimension_for_count(2), 1792)
        self.assertEqual(_image_dimension_for_count(4), 1536)
        self.assertEqual(_image_dimension_for_count(6), 1280)

    def test_agent_prompts_remain_bounded_and_structured(self):
        long_text = "全球定位线索" * 1000
        evidence = [
            Evidence(
                f"E{index}",
                "visual-clue-" + long_text,
                long_text,
                0.9,
                "vision",
                "region",
                [f"P{index % 6 + 1}"],
                long_text,
                [long_text] * 8,
                [long_text] * 8,
            )
            for index in range(1, 21)
        ]
        candidates = [
            Candidate.from_dict(
                {
                    "id": f"C{index}",
                    "name": long_text,
                    "country": long_text,
                    "region": long_text,
                    "latitude": index,
                    "longitude": index,
                    "initial_score": 0.8,
                    "radius_km": 100,
                    "evidence_ids": [f"E{index}"],
                    "rationale": long_text,
                },
                index - 1,
            )
            for index in range(1, 9)
        ]
        gis_results = {}
        for candidate in candidates:
            checks = [
                GISCheck(
                    f"check-{index}",
                    long_text,
                    long_text,
                    index % 3 == 0,
                    long_text,
                    detail=long_text,
                    required=index < 3,
                )
                for index in range(30)
            ]
            gis_results[candidate.candidate_id] = CandidateGISResult(
                candidate_id=candidate.candidate_id,
                reverse=ReversePlace(
                    display_name=long_text,
                    country=long_text,
                    region=long_text,
                    locality=long_text,
                    source=long_text,
                    aliases=[long_text] * 12,
                ),
                checks=checks,
                gis_score=0.8,
                coverage=0.75,
                verified=True,
                backend=long_text,
            )

        evidence_prompt = GeoAgentPipeline._evidence_user_prompt(
            long_text,
            evidence,
            ["/tmp/very-long-name.jpg"],
            "same_location",
        )
        candidate_prompt = GeoAgentPipeline._candidate_user_prompt(
            long_text,
            evidence,
            photo_count=6,
        )
        verify_prompt = GeoAgentPipeline._verify_user_prompt(
            long_text,
            evidence,
            candidates,
            gis_results,
        )

        self.assertLessEqual(
            len(evidence_prompt), EVIDENCE_PROMPT_CHAR_LIMIT
        )
        self.assertLessEqual(
            len(candidate_prompt), CANDIDATE_PROMPT_CHAR_LIMIT
        )
        self.assertLessEqual(len(verify_prompt), VERIFY_PROMPT_CHAR_LIMIT)
        self.assertIn("[truncated]", evidence_prompt)
        self.assertIn("[truncated]", candidate_prompt)
        self.assertIn("[truncated]", verify_prompt)
        json.loads(candidate_prompt.split("\n证据：", 1)[1])
        verification_tail = verify_prompt.split("\n证据：", 1)[1]
        evidence_json, candidate_json = verification_tail.split(
            "\n候选：", 1
        )
        json.loads(evidence_json)
        compact_candidates = json.loads(candidate_json)
        self.assertEqual(len(compact_candidates), 8)
        self.assertTrue(
            all(
                len(item["gis_verification"]["checks"]) <= 8
                for item in compact_candidates
            )
        )
        self.assertTrue(
            all(
                item["gis_verification"]["checks_total"] == 30
                for item in compact_candidates
            )
        )

    def test_duplicate_cross_photo_evidence_is_merged_without_double_counting(self):
        evidence = GeoAgentPipeline._parse_evidence(
            {
                "evidence": [
                    {
                        "id": "E1",
                        "kind": "road",
                        "value": "yellow center line",
                        "reliability": 0.7,
                        "photo_ids": ["P1"],
                    },
                    {
                        "id": "E2",
                        "kind": "road",
                        "value": "yellow center line",
                        "reliability": 0.9,
                        "photo_ids": ["P2"],
                    },
                ]
            },
            [],
        )
        self.assertEqual(len(evidence), 1)
        self.assertEqual(evidence[0].photo_ids, ["P1", "P2"])
        self.assertEqual(evidence[0].reliability, 0.9)

    def test_case_photo_count_is_bounded(self):
        paths = [f"/tmp/photo-{index}.jpg" for index in range(10)]
        self.assertEqual(
            GeoAgentPipeline._normalize_image_paths("", paths),
            paths[:6],
        )

    def test_plans_osm_constraints_from_chinese_and_english(self):
        constraints = plan_spatial_constraints(
            [],
            "寻找左侧通行、临海、near a volcano and vineyard 的城市",
        )
        self.assertEqual(
            {item.constraint_id for item in constraints},
            {"left_hand_traffic", "coastline", "volcano", "vineyard"},
        )
        self.assertTrue(all(item.required for item in constraints))

    def test_postgis_table_name_is_validated(self):
        self.assertEqual(
            PostGISConfig(dsn="x", table="public.osm").quoted_table,
            '"public"."osm"',
        )
        with self.assertRaises(PostGISError):
            PostGISConfig(dsn="x", table="public.osm;drop table x").quoted_table

    def test_overpass_query_uses_bounded_boxes_and_geometry(self):
        candidate = Candidate.from_dict(
            {
                "name": "Auckland",
                "latitude": -36.8485,
                "longitude": 174.7633,
                "initial_score": 0.5,
            },
            0,
        )
        constraint = plan_spatial_constraints([], "coastal city")[0]
        query = OSMServices._overpass_query([candidate], [constraint])
        self.assertNotIn("around:", query)
        self.assertIn('["natural"="coastline"]', query)
        self.assertIn("out geom", query)

    def test_country_mismatch_is_strongly_penalized(self):
        checks = [
            GISCheck(
                "reverse_country",
                "reverse_geocode",
                "country",
                False,
                "test",
            ),
            GISCheck(
                "reverse_locality",
                "reverse_geocode",
                "locality",
                True,
                "test",
            ),
        ]
        self.assertLess(GISVerifier._score(checks), 0.1)

    def test_unavailable_checks_are_neutral_and_reduce_coverage(self):
        checks = [
            GISCheck(
                "reverse_country",
                "reverse_geocode",
                "country",
                True,
                "test",
            ),
            GISCheck(
                "reverse_locality",
                "reverse_geocode",
                "locality",
                True,
                "test",
            ),
            GISCheck(
                "coastline",
                "spatial_constraint",
                "coastline",
                None,
                "unavailable",
            ),
        ]
        self.assertAlmostEqual(GISVerifier._score(checks), 1.0)
        self.assertAlmostEqual(GISVerifier._coverage(checks), 0.25)

    def test_low_gis_coverage_shrinks_to_neutral_prior(self):
        evidence = [
            Evidence(
                "E1",
                "road",
                "left-hand traffic",
                0.8,
                "vision",
                "country",
            )
        ]
        unavailable = Candidate.from_dict(
            {
                "name": "A",
                "latitude": 0,
                "longitude": 0,
                "initial_score": 0.7,
            },
            0,
        )
        unavailable.model_verification_score = 0.8
        unavailable.gis_score = 1.0
        unavailable.gis_coverage = 0.0
        unavailable.gis_verified = True
        verified = Candidate.from_dict(
            {
                "name": "B",
                "latitude": 20,
                "longitude": 20,
                "initial_score": 0.7,
            },
            1,
        )
        verified.model_verification_score = 0.8
        verified.gis_score = 0.7
        verified.gis_coverage = 1.0
        verified.gis_verified = True
        fuse_candidate_score(unavailable, evidence)
        fuse_candidate_score(verified, evidence)
        self.assertGreater(verified.ranking_score, unavailable.ranking_score)
        self.assertEqual(unavailable.ranking_components["effective_gis"], 0.5)

    def test_country_mismatch_caps_final_ranking(self):
        candidate = Candidate.from_dict(
            {
                "name": "Wrong country",
                "latitude": 1,
                "longitude": 1,
                "initial_score": 0.99,
            },
            0,
        )
        candidate.model_verification_score = 0.99
        candidate.gis_score = 0.8
        candidate.gis_coverage = 1.0
        candidate.gis_verified = True
        candidate.gis_checks = [
            GISCheck(
                "reverse_country",
                "reverse_geocode",
                "country",
                False,
                "test",
            )
        ]
        fuse_candidate_score(
            candidate,
            [
                Evidence(
                    "E1",
                    "landmark",
                    "distinct landmark",
                    1.0,
                    "local-metadata",
                    "point",
                )
            ],
        )
        self.assertEqual(candidate.ranking_score, 0.18)

    def test_required_spatial_mismatch_caps_final_ranking(self):
        candidate = Candidate.from_dict(
            {
                "name": "No nearby volcano",
                "latitude": 1,
                "longitude": 1,
                "initial_score": 0.95,
            },
            0,
        )
        candidate.model_verification_score = 0.95
        candidate.gis_score = 0.85
        candidate.gis_coverage = 1.0
        candidate.gis_verified = True
        candidate.gis_checks = [
            GISCheck(
                "volcano",
                "spatial_constraint",
                "volcano",
                False,
                "OSM Overpass",
                required=True,
            )
        ]
        fuse_candidate_score(candidate, [])
        self.assertEqual(candidate.ranking_score, 0.5)
        self.assertEqual(candidate.ranking_components["required_mismatches"], 1)

    def test_unverified_required_constraints_cap_overconfident_ranking(self):
        candidate = Candidate.from_dict(
            {
                "name": "Unverified",
                "latitude": 1,
                "longitude": 1,
                "initial_score": 0.99,
            },
            0,
        )
        candidate.model_verification_score = 0.99
        candidate.gis_score = 1.0
        candidate.gis_coverage = 0.8
        candidate.gis_verified = True
        candidate.gis_checks = [
            GISCheck(
                "volcano",
                "spatial_constraint",
                "volcano",
                None,
                "OSM Overpass unavailable",
                required=True,
            )
        ]
        fuse_candidate_score(
            candidate,
            [
                Evidence(
                    "E1",
                    "landmark",
                    "distinct landmark",
                    1.0,
                    "local-metadata",
                    "point",
                )
            ],
        )
        self.assertEqual(candidate.ranking_score, 0.85)
        self.assertEqual(candidate.ranking_components["required_unknowns"], 1)

    def test_candidate_selection_removes_near_duplicates_and_keeps_diversity(self):
        candidates = [
            Candidate.from_dict(
                {
                    "name": "Tokyo",
                    "country": "Japan",
                    "latitude": 35.6762,
                    "longitude": 139.6503,
                    "initial_score": 0.9,
                },
                0,
            ),
            Candidate.from_dict(
                {
                    "name": "Shinjuku",
                    "country": "Japan",
                    "latitude": 35.6938,
                    "longitude": 139.7034,
                    "initial_score": 0.8,
                },
                1,
            ),
            Candidate.from_dict(
                {
                    "name": "Auckland",
                    "country": "New Zealand",
                    "latitude": -36.8485,
                    "longitude": 174.7633,
                    "initial_score": 0.65,
                },
                2,
            ),
        ]
        selected = select_diverse_candidates(candidates)
        self.assertEqual([item.name for item in selected], ["Tokyo", "Auckland"])
        self.assertEqual([item.candidate_id for item in selected], ["C1", "C2"])

    def test_geometry_distance_uses_line_segments_not_only_vertices(self):
        distance = _distance_to_feature_km(
            0.0, 0.0, [(1.0, -1.0), (1.0, 1.0)]
        )
        self.assertAlmostEqual(distance, 111.2, delta=0.5)

    def test_overpass_boxes_wrap_across_dateline(self):
        boxes = OSMServices._bounding_boxes(0.0, 179.8, 100.0)
        self.assertEqual(len(boxes), 2)
        self.assertEqual(boxes[0][3], 180.0)
        self.assertEqual(boxes[1][1], -180.0)

    def test_runtime_language_switch(self):
        set_language("en")
        self.assertEqual(tr("menu.file"), "File")
        self.assertEqual(tr("menu.appearance"), "Appearance")
        self.assertEqual(tr("theme.light"), "Light Mode")
        set_language("zh_CN")
        self.assertEqual(tr("menu.file"), "文件")
        self.assertEqual(tr("menu.appearance"), "外观")
        self.assertEqual(tr("theme.light"), "浅色模式")

    def test_profile_csv_parser(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile.csv"
            path.write_text(
                "apiKey,test-api-key-not-a-secret\n"
                "openAiCompatible,https://example.invalid/compatible-mode/v1\n"
                "workspaceId,ws-example\n",
                encoding="utf-8",
            )
            profile = load_profile_csv(str(path))
        self.assertEqual(profile.workspace_id, "ws-example")
        self.assertEqual(
            profile.base_url, "https://example.invalid/compatible-mode/v1"
        )


if __name__ == "__main__":
    unittest.main()
