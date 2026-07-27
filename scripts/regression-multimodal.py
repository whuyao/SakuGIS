#!/usr/bin/env python3
"""Run repeatable multimodal end-to-end regression cases for SakuGIS."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

from sakugis.geo_agents import GeoAgentPipeline
from sakugis.i18n import set_language
from sakugis.place_search import (
    BraveSearchClient,
    PlaceSearchError,
    has_named_gis_identity,
    has_online_place_material,
)
from sakugis.qwen_client import QwenClient
from sakugis.ranking import haversine_km
from sakugis.reporting import write_markdown_report


class AuditedQwenClient(QwenClient):
    def __init__(self):
        super().__init__()
        self.audit: List[Dict[str, Any]] = []

    def chat_json(self, *args, **kwargs):
        started = time.perf_counter()
        error = ""
        try:
            return super().chat_json(*args, **kwargs)
        except Exception as exc:
            error = type(exc).__name__
            raise
        finally:
            entry = dict(self.last_request_stats)
            entry["duration_seconds"] = round(
                time.perf_counter() - started, 3
            )
            entry["error"] = error
            self.audit.append(entry)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument(
        "--language", choices=("zh_CN", "en"), default="zh_CN"
    )
    arguments = parser.parse_args()

    manifest_path = Path(arguments.manifest).resolve()
    output_dir = Path(arguments.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    cases = manifest.get("cases")
    if not isinstance(cases, list) or not cases:
        raise SystemExit("Manifest must contain a non-empty cases list.")

    set_language(arguments.language)
    results: List[Dict[str, Any]] = []
    started_all = time.perf_counter()
    for index, case in enumerate(cases, 1):
        result = run_case(
            case,
            index=index,
            total=len(cases),
            output_dir=output_dir,
            language=arguments.language,
        )
        results.append(result)
        write_aggregate(
            output_dir,
            manifest_path,
            results,
            time.perf_counter() - started_all,
        )

    core_passed = sum(bool(item.get("core_pass")) for item in results)
    print(
        f"REGRESSION_DONE core={core_passed}/{len(results)} "
        f"output={output_dir}",
        flush=True,
    )
    return 0 if core_passed == len(results) else 2


def run_case(
    case: Dict[str, Any],
    index: int,
    total: int,
    output_dir: Path,
    language: str,
) -> Dict[str, Any]:
    case_id = str(case.get("id") or f"case-{index}")
    label = str(case.get("label") or case_id)
    image_paths = [str(Path(path).resolve()) for path in case.get("images", [])]
    missing = [path for path in image_paths if not Path(path).is_file()]
    print(
        f"CASE_START {index}/{total} id={case_id} "
        f"photos={len(image_paths)} label={label}",
        flush=True,
    )
    if missing:
        return failure(case_id, label, f"missing images: {missing}")

    qwen = AuditedQwenClient()
    progress: List[Dict[str, Any]] = []
    case_started = time.perf_counter()

    def on_progress(percent: int, message: str) -> None:
        elapsed = round(time.perf_counter() - case_started, 3)
        progress.append(
            {"percent": percent, "message": message, "elapsed": elapsed}
        )
        print(
            f"CASE_PROGRESS id={case_id} percent={percent} "
            f"elapsed={elapsed:.1f}s message={message}",
            flush=True,
        )

    try:
        pipeline_result = GeoAgentPipeline(client=qwen).run(
            image_paths=image_paths,
            query=str(case.get("query") or ""),
            progress=on_progress,
        )
    except Exception as exc:
        result = failure(case_id, label, f"{type(exc).__name__}: {exc}")
        result.update(
            {
                "duration_seconds": round(
                    time.perf_counter() - case_started, 3
                ),
                "progress": progress,
                "qwen_calls": qwen.audit,
            }
        )
        print(
            f"CASE_FAILED id={case_id} error={result['error']}",
            flush=True,
        )
        return result

    expected = case.get("expected") or {}
    expected_latitude = float(expected["latitude"])
    expected_longitude = float(expected["longitude"])
    candidates = pipeline_result.candidates
    distances = [
        haversine_km(
            expected_latitude,
            expected_longitude,
            candidate.latitude,
            candidate.longitude,
        )
        for candidate in candidates
    ]
    top1_distance = distances[0] if distances else float("inf")
    top3_distance = min(distances[:3], default=float("inf"))
    expected_rank = (
        min(range(len(distances)), key=distances.__getitem__) + 1
        if distances
        else 0
    )

    expected_photo_ids = {
        f"P{photo_index}"
        for photo_index in range(1, len(image_paths) + 1)
    }
    vision_photo_ids = {
        photo_id
        for evidence in pipeline_result.evidence
        if evidence.source.casefold() in {"vision", "ocr", "qwen"}
        for photo_id in evidence.photo_ids
    }
    all_photo_ids = {
        photo_id
        for evidence in pipeline_result.evidence
        for photo_id in evidence.photo_ids
    }

    top1 = candidates[0] if candidates else None
    online: Dict[str, Any] = {
        "attempted": False,
        "eligible": False,
        "web_results": 0,
        "images": 0,
        "thumbnail_bytes": 0,
        "warnings": [],
        "error": "",
    }
    if top1 is not None:
        online["eligible"] = has_named_gis_identity(top1)
        online["attempted"] = True
        try:
            brave = BraveSearchClient()
            details = brave.search_place(
                top1, language, force_refresh=True
            )
            online["web_results"] = len(details.web_results)
            online["images"] = len(details.images)
            online["warnings"] = list(details.warnings)
            online["has_material"] = has_online_place_material(details)
            if details.images:
                thumbnail = brave.fetch_thumbnail(
                    details.images[0].thumbnail_url
                )
                online["thumbnail_bytes"] = len(thumbnail)
        except PlaceSearchError as exc:
            online["error"] = exc.code
        except Exception as exc:
            online["error"] = type(exc).__name__

    top1_limit = float(expected.get("top1_max_km", 50.0))
    top3_limit = float(expected.get("top3_max_km", top1_limit * 3.0))
    checks = {
        "candidate_returned": bool(candidates),
        "top1_within_threshold": top1_distance <= top1_limit,
        "top3_contains_expected_area": top3_distance <= top3_limit,
        "all_photos_have_evidence": expected_photo_ids <= all_photo_ids,
        "all_photos_have_visual_evidence": (
            expected_photo_ids <= vision_photo_ids
        ),
        "real_place_resolved": pipeline_result.retrieval_resolved_count > 0,
        "top1_gis_verified": bool(top1 and top1.gis_verified),
        "top1_gis_has_coverage": bool(
            top1 and top1.gis_coverage > 0.0
        ),
    }
    core_pass = all(checks.values())
    enrichment_pass = bool(
        online.get("has_material")
        and (
            online.get("web_results", 0) > 0
            or online.get("images", 0) > 0
        )
        and (
            online.get("images", 0) == 0
            or online.get("thumbnail_bytes", 0) > 0
        )
    )

    case_slug = safe_slug(case_id)
    write_markdown_report(
        str(output_dir / f"{case_slug}-pipeline.md"),
        pipeline_result,
    )
    raw_path = output_dir / f"{case_slug}-pipeline.json"
    raw_path.write_text(
        json.dumps(
            pipeline_result.to_dict(),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    result = {
        "id": case_id,
        "label": label,
        "status": "passed" if core_pass else "failed",
        "core_pass": core_pass,
        "enrichment_pass": enrichment_pass,
        "duration_seconds": round(
            time.perf_counter() - case_started, 3
        ),
        "photo_count": len(image_paths),
        "photo_names": [Path(path).name for path in image_paths],
        "query": str(case.get("query") or ""),
        "evidence_count": len(pipeline_result.evidence),
        "all_evidence_photo_ids": sorted(all_photo_ids),
        "visual_evidence_photo_ids": sorted(vision_photo_ids),
        "candidate_count": len(candidates),
        "top1": candidate_summary(top1, top1_distance),
        "expected_rank": expected_rank,
        "top1_distance_km": round(top1_distance, 3),
        "top3_min_distance_km": round(top3_distance, 3),
        "top1_limit_km": top1_limit,
        "top3_limit_km": top3_limit,
        "retrieval_backend": pipeline_result.retrieval_backend,
        "retrieval_resolved_count": pipeline_result.retrieval_resolved_count,
        "gis_backend": pipeline_result.gis_backend,
        "checks": checks,
        "online": online,
        "qwen_calls": qwen.audit,
        "qwen_retry_count": sum(
            int(item.get("retry_count", 0)) for item in qwen.audit
        ),
        "progress": progress,
        "candidates": [
            candidate_summary(candidate, distance)
            for candidate, distance in zip(candidates, distances)
        ],
    }
    print(
        f"CASE_DONE id={case_id} core_pass={core_pass} "
        f"enrichment_pass={enrichment_pass} "
        f"top1={result['top1'].get('name', '—')} "
        f"distance_km={top1_distance:.1f} "
        f"resolved={pipeline_result.retrieval_resolved_count}/"
        f"{len(candidates)} web={online['web_results']} "
        f"images={online['images']} retries={result['qwen_retry_count']}",
        flush=True,
    )
    return result


def candidate_summary(candidate, distance: float) -> Dict[str, Any]:
    if candidate is None:
        return {}
    return {
        "id": candidate.candidate_id,
        "name": candidate.name,
        "country": candidate.country,
        "region": candidate.region,
        "latitude": candidate.latitude,
        "longitude": candidate.longitude,
        "distance_to_expected_km": round(distance, 3),
        "composite_score": round(candidate.ranking_score, 4),
        "retrieval_score": round(candidate.retrieval_score, 4),
        "retrieval_source": candidate.retrieval_source,
        "retrieval_verified": candidate.retrieval_verified,
        "gis_score": round(candidate.gis_score, 4),
        "gis_coverage": round(candidate.gis_coverage, 4),
        "gis_verified": candidate.gis_verified,
        "photo_support_count": candidate.photo_support_count,
        "photo_total_count": candidate.photo_total_count,
        "contradiction_count": len(candidate.contradictions),
    }


def failure(case_id: str, label: str, error: str) -> Dict[str, Any]:
    return {
        "id": case_id,
        "label": label,
        "status": "error",
        "core_pass": False,
        "enrichment_pass": False,
        "error": error,
    }


def write_aggregate(
    output_dir: Path,
    manifest_path: Path,
    results: List[Dict[str, Any]],
    duration_seconds: float,
) -> None:
    payload = {
        "manifest": str(manifest_path),
        "duration_seconds": round(duration_seconds, 3),
        "case_count": len(results),
        "core_pass_count": sum(
            bool(item.get("core_pass")) for item in results
        ),
        "enrichment_pass_count": sum(
            bool(item.get("enrichment_pass")) for item in results
        ),
        "results": results,
    }
    (output_dir / "regression-results.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    lines = [
        "# SakuGIS 多模态全流程回归",
        "",
        f"- 已运行案例：{len(results)}",
        f"- 核心链路通过：{payload['core_pass_count']}/{len(results)}",
        (
            f"- 网络资料链路通过："
            f"{payload['enrichment_pass_count']}/{len(results)}"
        ),
        f"- 累计耗时：{duration_seconds:.1f} 秒",
        "",
        "| 案例 | 结果 | Top-1 | 误差 | 地点解析 | GIS | 网页/图片 | 重试 |",
        "|---|---|---|---:|---:|---|---:|---:|",
    ]
    for item in results:
        top1 = item.get("top1") or {}
        online = item.get("online") or {}
        lines.append(
            "| {label} | {status} | {top1} | {distance} | "
            "{resolved}/{candidates} | {gis} | {web}/{images} | {retry} |".format(
                label=escape_cell(item.get("label", item.get("id", "—"))),
                status=("通过" if item.get("core_pass") else "失败"),
                top1=escape_cell(top1.get("name", "—")),
                distance=(
                    f"{item['top1_distance_km']:.1f} km"
                    if "top1_distance_km" in item
                    else "—"
                ),
                resolved=item.get("retrieval_resolved_count", 0),
                candidates=item.get("candidate_count", 0),
                gis=(
                    f"{top1.get('gis_score', 0.0) * 100:.1f}/"
                    f"{top1.get('gis_coverage', 0.0) * 100:.0f}%"
                    if top1
                    else "—"
                ),
                web=online.get("web_results", 0),
                images=online.get("images", 0),
                retry=item.get("qwen_retry_count", 0),
            )
        )
    lines.extend(["", "## 逐案例检查", ""])
    for item in results:
        lines.append(f"### {item.get('label', item.get('id', '—'))}")
        lines.append("")
        if item.get("error"):
            lines.append(f"- 错误：{item['error']}")
        for name, passed in (item.get("checks") or {}).items():
            lines.append(f"- {'通过' if passed else '失败'}：`{name}`")
        online = item.get("online") or {}
        if online:
            lines.append(
                "- 网络资料：网页 {web}，图片 {images}，首图 "
                "{thumbnail} bytes，警告 {warnings}，错误 {error}".format(
                    web=online.get("web_results", 0),
                    images=online.get("images", 0),
                    thumbnail=online.get("thumbnail_bytes", 0),
                    warnings=", ".join(online.get("warnings", [])) or "无",
                    error=online.get("error") or "无",
                )
            )
        lines.append("")
    (output_dir / "regression-report.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def safe_slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-")
    return slug or "case"


def escape_cell(value: Any) -> str:
    return str(value or "—").replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    sys.exit(main())
