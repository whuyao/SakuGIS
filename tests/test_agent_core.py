import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from sakugis.agent_models import Candidate, Evidence
from sakugis.credentials import load_profile_csv
from sakugis.geo_agents import GeoAgentPipeline
from sakugis.gis_models import CandidateGISResult, GISCheck, ReversePlace
from sakugis.gis_verifier import GISVerifier
from sakugis.i18n import set_language, tr
from sakugis.osm_services import OSMServices, _distance_to_feature_km
from sakugis.postgis_provider import PostGISConfig, PostGISError
from sakugis.qwen_client import extract_json_object
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
            (system_prompt, user_prompt, image_path, list(image_paths or []))
        )
        if len(self.calls) == 1:
            photo_ids = [
                f"P{index}"
                for index, _path in enumerate(image_paths or [], 1)
            ]
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
        if len(self.calls) == 2:
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
        return {
            "summary": "奥克兰最符合当前证据",
            "caveat": "尚未检查参考影像",
            "candidates": [
                {
                    "id": "C1",
                    "evidence_score": 0.9,
                    "radius_km": 50,
                    "supporting_evidence": ["E1"],
                    "contradictions": [],
                    "rationale": "左侧通行且临海",
                }
            ],
        }


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


class AgentCoreTests(unittest.TestCase):
    def test_extracts_fenced_json(self):
        self.assertEqual(
            extract_json_object('```json\n{"answer": 42}\n```'),
            {"answer": 42},
        )

    def test_candidate_rejects_invalid_coordinates(self):
        with self.assertRaises(ValueError):
            Candidate.from_dict({"latitude": 91, "longitude": 0}, 0)

    def test_pipeline_runs_three_agents_and_marks_result_uncalibrated(self):
        client = FakeQwenClient()
        result = GeoAgentPipeline(client, FakeGISVerifier()).run(
            query="寻找左侧通行且临海的城市"
        )
        self.assertEqual(len(client.calls), 3)
        self.assertEqual(len(result.candidates), 1)
        self.assertEqual(result.candidates[0].name, "奥克兰")
        self.assertAlmostEqual(result.candidates[0].ranking_score, 0.7478)
        self.assertEqual(result.confidence_status, "uncalibrated")
        self.assertEqual(result.gis_backend, "fake-postgis")
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
        result = GeoAgentPipeline(client, FakeGISVerifier()).run(
            image_paths=paths,
            query="这两张照片拍摄于同一地点",
        )
        candidate = result.candidates[0]
        self.assertEqual(result.image_paths, paths)
        self.assertEqual(result.image_path, paths[0])
        self.assertEqual(client.calls[0][3], paths)
        self.assertEqual(candidate.photo_support_count, 2)
        self.assertEqual(candidate.photo_total_count, 2)
        self.assertEqual(candidate.photo_consistency, 1.0)
        self.assertIn("跨照片覆盖", build_markdown_report(result))

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
        set_language("zh_CN")
        self.assertEqual(tr("menu.file"), "文件")

    def test_profile_csv_parser(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile.csv"
            path.write_text(
                "apiKey,sk-test-abcdefghijklmnopqrstuvwxyz\n"
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
