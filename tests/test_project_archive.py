import json
from pathlib import Path
import tempfile
import unittest
from zipfile import ZIP_DEFLATED, ZipFile

from sakugis.agent_models import Candidate, Evidence, GeoAnalysisResult
from sakugis.gis_models import GISCheck, SpatialConstraint
from sakugis.project_archive import (
    ArchiveAsset,
    SgdFormatError,
    SgdIntegrityError,
    load_sgd,
    save_sgd,
)


def _result(photo: str) -> GeoAnalysisResult:
    candidate = Candidate(
        candidate_id="C1",
        name="黄鹤楼",
        country="中国",
        region="湖北省武汉市",
        latitude=30.5445,
        longitude=114.3046,
        initial_score=0.82,
        ranking_score=0.88,
        radius_km=8,
        country_code="CN",
        model_verification_score=0.86,
        gis_score=0.91,
        gis_coverage=1.0,
        gis_verified=True,
        reverse_label="黄鹤楼，武汉市，中国",
        gis_backend="OSM",
        gis_checks=[
            GISCheck(
                check_id="reverse_country",
                kind="reverse_geocode",
                label="国家反查",
                matched=True,
                source="OSM",
                nearest_distance_km=0.1,
                strength=0.95,
            )
        ],
        ranking_components={"evidence": 0.86, "gis": 0.91},
        photo_support_count=1,
        photo_total_count=1,
        supporting_evidence=["E1"],
        rationale="地标轮廓与江岸环境一致。",
        retrieval_source="OSM Nominatim",
        retrieval_label="Yellow Crane Tower",
        retrieval_score=0.94,
        retrieval_verified=True,
    )
    return GeoAnalysisResult(
        query="识别照片中的中国历史建筑",
        image_path=photo,
        image_paths=[photo],
        evidence_summary="照片中出现多层黄瓦古典楼阁。",
        evidence=[
            Evidence(
                evidence_id="E1",
                kind="architecture",
                value="多层黄瓦楼阁",
                reliability=0.9,
                source="photo",
                photo_ids=["P1"],
            )
        ],
        candidates=[candidate],
        verification_summary="OSM 地点和空间环境支持黄鹤楼。",
        caveat="置信度未经统计校准。",
        model="qwen-test",
        gis_backend="OSM",
        retrieval_backend="OSM Nominatim",
        retrieval_resolved_count=1,
        spatial_constraints=[
            SpatialConstraint(
                constraint_id="near_river",
                kind="near_feature",
                label="临近河流",
                radius_km=3,
                tag_key="waterway",
                evidence_ids=["E1"],
            )
        ],
    )


class ProjectArchiveTests(unittest.TestCase):
    def test_round_trip_packages_inputs_result_and_local_layer(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            photo = root / "武汉 照片.jpg"
            photo.write_bytes(b"fake-jpeg-content")
            geojson = root / "study.geojson"
            geojson.write_text('{"type":"FeatureCollection","features":[]}', encoding="utf-8")
            thumbnail = root / "thumbnail.webp"
            thumbnail.write_bytes(b"fake-web-thumbnail")
            project_path = root / "case.sgd"
            map_state = {
                "canvas": {"crs": "EPSG:3857", "extent_wgs84": [113, 29, 115, 31]},
                "layers": [
                    {
                        "name": "研究范围",
                        "kind": "vector",
                        "provider": "ogr",
                        "archive_primary": "layers/L1/study.geojson",
                        "visible": True,
                    }
                ],
            }

            saved = save_sgd(
                str(project_path),
                query="识别照片中的中国历史建筑",
                image_paths=[str(photo)],
                result=_result(str(photo)),
                map_state=map_state,
                place_details={
                    "candidates": {
                        "C1": {
                            "candidate_id": "C1",
                            "query": "黄鹤楼 武汉",
                            "web_results": [
                                {
                                    "title": "黄鹤楼介绍",
                                    "url": "https://example.com/place",
                                    "description": "武汉历史地标",
                                    "source": "example.com",
                                }
                            ],
                            "images": [],
                            "warnings": [],
                            "thumbnails": [
                                {
                                    "index": 0,
                                    "archive_path": "places/C1/thumbnail-1.img",
                                }
                            ],
                        }
                    }
                },
                assets=[
                    ArchiveAsset(str(geojson), "layers/L1/study.geojson"),
                    ArchiveAsset(str(thumbnail), "places/C1/thumbnail-1.img"),
                ],
                application_version="0.4.0-test",
            )
            loaded = load_sgd(str(saved), str(root / "extracted"))

            self.assertEqual(loaded.query, "识别照片中的中国历史建筑")
            self.assertEqual(Path(loaded.image_paths[0]).read_bytes(), photo.read_bytes())
            self.assertEqual(loaded.result.candidates[0].ranking_score, 0.88)
            self.assertTrue(loaded.result.candidates[0].gis_verified)
            self.assertEqual(loaded.result.candidates[0].gis_checks[0].matched, True)
            self.assertEqual(loaded.result.image_paths, loaded.image_paths)
            self.assertTrue((loaded.extraction_root / "layers/L1/study.geojson").is_file())
            self.assertEqual(
                loaded.place_details["candidates"]["C1"]["web_results"][0]["title"],
                "黄鹤楼介绍",
            )
            self.assertTrue(
                (loaded.extraction_root / "places/C1/thumbnail-1.img").is_file()
            )
            self.assertEqual(loaded.process["stages"][2]["check_count"], 1)

            with ZipFile(saved) as archive:
                names = set(archive.namelist())
                manifest = json.loads(archive.read("manifest.json"))
                serialized = archive.read("analysis/result.json").decode("utf-8")
            self.assertIn("photos/P1.jpg", names)
            self.assertIn("report/report.md", names)
            self.assertFalse(manifest["privacy"]["credentials_included"])
            self.assertNotIn(str(root), serialized)

    def test_checksum_tampering_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "photo.jpg"
            source.write_bytes(b"original")
            project = save_sgd(
                str(root / "case.sgd"),
                query="test",
                image_paths=[str(source)],
                result=None,
            )
            entries = {}
            with ZipFile(project) as archive:
                for name in archive.namelist():
                    entries[name] = archive.read(name)
            entries["photos/P1.jpg"] = b"tampered"
            with ZipFile(project, "w", compression=ZIP_DEFLATED) as archive:
                for name, content in entries.items():
                    archive.writestr(name, content)

            with self.assertRaises(SgdIntegrityError):
                load_sgd(str(project), str(root / "extracted"))

    def test_path_traversal_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "bad.sgd"
            with ZipFile(project, "w") as archive:
                archive.writestr("../outside", b"bad")
            with self.assertRaises(SgdFormatError):
                load_sgd(str(project), str(root / "extracted"))


if __name__ == "__main__":
    unittest.main()
