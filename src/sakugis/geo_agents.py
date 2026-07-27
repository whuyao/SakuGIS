"""Three-stage Qwen-assisted geolocation pipeline."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from sakugis.agent_models import (
    MAX_CASE_PHOTOS,
    Candidate,
    Evidence,
    GeoAnalysisResult,
    clamp,
)
from sakugis.gis_models import CandidateGISResult
from sakugis.gis_verifier import GISVerifier
from sakugis.i18n import EN, get_language, tr
from sakugis.photo_metadata import extract_photo_metadata
from sakugis.prompt_budget import (
    CANDIDATE_PROMPT_CHAR_LIMIT,
    EVIDENCE_PROMPT_CHAR_LIMIT,
    VERIFY_PROMPT_CHAR_LIMIT,
    build_bounded_prompt,
    compact_json,
    compact_text_list,
    shorten_text,
)
from sakugis.qwen_client import QwenClient
from sakugis.ranking import fuse_candidate_score, select_diverse_candidates
from sakugis.spatial_constraints import plan_spatial_constraints


ProgressCallback = Callable[[int, str], None]
EVIDENCE_MAX_OUTPUT_TOKENS = 3072
CANDIDATE_MAX_OUTPUT_TOKENS = 3072
VERIFY_MAX_OUTPUT_TOKENS = 4096


EVIDENCE_SYSTEM_PROMPT = """
你是 SakuGIS Agent 1：地理证据提取器。分析输入照片和查询，但不要直接给出
最终地点。只报告可以从输入观察或可靠推断的证据；不确定时降低 reliability，
不得编造看不见的文字。输出严格 JSON：
{
  "summary": "简短证据摘要",
  "evidence": [
    {
      "id": "E1",
      "kind": "ocr|language|road|traffic|architecture|terrain|vegetation|climate|landmark|query",
      "value": "证据内容",
      "reliability": 0.0,
      "source": "vision|ocr|user-query",
      "scale": "point|city|region|country|global|context",
      "photo_ids": ["P1"],
      "correlation_group": "同一物体或线索组的稳定名称",
      "supports": ["支持的地区或约束"],
      "contradicts": ["排除的地区或约束"]
    }
  ]
}
reliability 只表示该证据识别是否可靠，不是地点概率。提示中会给出当前照片
的稳定编号 P1、P2…，每条证据必须使用该编号；跨照片证据由 SakuGIS 在本机
合并，避免重复计分。每张照片最多返回 8 条最有区分度的证据。
""".strip()


CANDIDATE_SYSTEM_PROMPT = """
你是 SakuGIS Agent 2：全球候选生成器。根据结构化证据和用户查询，从全球范围
生成彼此不同的候选地点。必须给出有效 WGS84 经纬度。优先让候选覆盖不同合理
假设，不要假装已经访问实时地图或私有数据库。输出严格 JSON：
{
  "candidates": [
    {
      "id": "C1",
      "name": "地点名称",
      "country": "国家",
      "country_code": "ISO 3166-1 alpha-2，例如 JP",
      "region": "城市或行政区",
      "latitude": 0.0,
      "longitude": 0.0,
      "initial_score": 0.0,
      "radius_km": 100.0,
      "evidence_ids": ["E1"],
      "rationale": "进入候选集的理由"
    }
  ]
}
返回 6 至 12 个候选，主动覆盖多个不同国家或地区的合理假设，避免只给同一
都市圈内的近邻地点。initial_score 是未校准的相对检索分数，不是概率。
多照片输入默认来自同一拍摄地点。候选必须同时解释尽可能多的照片，不得只依赖
其中最容易识别的一张；理由中明确说明跨照片的一致性或冲突。
""".strip()


VERIFY_SYSTEM_PROMPT = """
你是 SakuGIS Agent 3：候选验证器。逐一对照照片/查询证据和 SakuGIS 提供的
真实 GIS 核验结果审查候选，找出支持项和矛盾项。GIS 数据来自 OSM Nominatim、
Overpass 或 PostGIS，优先于模型记忆；matched=null 表示服务不可用，不能当作
不匹配，也不能当作已满足；存在 null 时不得称为“完全匹配”。只有提示中实际
出现的证据 ID 才能写入 supporting_evidence。不得声称访问提示中没有提供的
数据。保留候选 id，输出严格 JSON：
{
  "summary": "总体判断",
  "caveat": "最重要的不确定性",
  "candidates": [
    {
      "id": "C1",
      "evidence_score": 0.0,
      "radius_km": 100.0,
      "supporting_evidence": ["E1"],
      "contradictions": ["具体矛盾"],
      "rationale": "验证结论"
    }
  ]
}
evidence_score 只衡量照片和查询证据对该候选的支持程度，不要把 GIS 分数再次
计入；SakuGIS 会在模型返回后确定性融合 GIS。该分数不是统计概率；证据不足时
扩大 radius_km。多照片输入时必须检查每张照片；supporting_evidence 应覆盖
候选真正能够解释的全部照片来源，无法解释的照片应写入 contradictions。
提示中的 GIS 检查可能经过长度压缩，但 gis_score 和 coverage 已由 SakuGIS
使用完整检查集确定；不得根据缺省的明细自行补充事实。
""".strip()


class GeoAgentPipeline:
    def __init__(
        self,
        client: Optional[QwenClient] = None,
        gis_verifier: Optional[GISVerifier] = None,
    ):
        self.client = client or QwenClient()
        self.gis_verifier = gis_verifier or GISVerifier()

    def run(
        self,
        image_path: str = "",
        image_paths: Optional[List[str]] = None,
        query: str = "",
        case_mode: str = "same_location",
        progress: Optional[ProgressCallback] = None,
    ) -> GeoAnalysisResult:
        cleaned_query = query.strip()
        paths = self._normalize_image_paths(image_path, image_paths)
        if not paths and not cleaned_query:
            raise ValueError(tr("agent.input_needed_detail"))

        self._progress(progress, 5, tr("progress.metadata"))
        local_evidence: List[Evidence] = []
        for index, path in enumerate(paths, 1):
            photo_id = f"P{index}"
            for item in extract_photo_metadata(path):
                item.evidence_id = f"{photo_id}-{item.evidence_id}"
                item.photo_ids = [photo_id]
                item.correlation_group = item.kind
                local_evidence.append(item)

        self._progress(progress, 15, tr("progress.agent1"))
        if paths:
            remote_evidence: List[Dict[str, Any]] = []
            evidence_summaries: List[str] = []
            for index, path in enumerate(paths, 1):
                photo_id = f"P{index}"
                local_for_photo = [
                    item
                    for item in local_evidence
                    if photo_id in item.photo_ids
                ]
                evidence_payload = self.client.chat_json(
                    EVIDENCE_SYSTEM_PROMPT,
                    self._evidence_user_prompt(
                        cleaned_query,
                        local_for_photo,
                        [path],
                        case_mode,
                        photo_ids=[photo_id],
                    ),
                    image_paths=[path],
                    max_tokens=EVIDENCE_MAX_OUTPUT_TOKENS,
                )
                summary = shorten_text(
                    evidence_payload.get("summary"), 320
                )
                if summary:
                    evidence_summaries.append(f"[{photo_id}] {summary}")
                raw = evidence_payload.get("evidence")
                for remote_index, item in enumerate(
                    raw if isinstance(raw, list) else []
                ):
                    if remote_index >= 8 or not isinstance(item, dict):
                        break
                    compacted = dict(item)
                    compacted["id"] = (
                        f"{photo_id}-"
                        f"{shorten_text(compacted.get('id') or remote_index + 1, 16)}"
                    )
                    compacted["photo_ids"] = [photo_id]
                    remote_evidence.append(compacted)
                self._progress(
                    progress,
                    15 + int(index / len(paths) * 24),
                    tr(
                        "progress.agent1_photo",
                        current=index,
                        total=len(paths),
                    ),
                )
            combined_evidence_payload = {
                "evidence": remote_evidence,
            }
            evidence = self._parse_evidence(
                combined_evidence_payload, local_evidence, limit=60
            )
            evidence = self._select_case_evidence(
                evidence,
                [f"P{index}" for index in range(1, len(paths) + 1)],
            )
            evidence_summary = shorten_text(
                "；".join(evidence_summaries), 1200
            )
        else:
            evidence_payload = self.client.chat_json(
                EVIDENCE_SYSTEM_PROMPT,
                self._evidence_user_prompt(
                    cleaned_query,
                    local_evidence,
                    [],
                    case_mode,
                ),
                max_tokens=EVIDENCE_MAX_OUTPUT_TOKENS,
            )
            evidence = self._parse_evidence(
                evidence_payload, local_evidence
            )
            evidence_summary = shorten_text(
                evidence_payload.get("summary"), 1200
            )

        self._progress(progress, 42, tr("progress.agent2"))
        candidate_payload = self.client.chat_json(
            CANDIDATE_SYSTEM_PROMPT,
            self._candidate_user_prompt(
                cleaned_query,
                evidence,
                photo_count=len(paths),
                case_mode=case_mode,
            ),
            max_tokens=CANDIDATE_MAX_OUTPUT_TOKENS,
        )
        candidates = self._parse_candidates(candidate_payload)
        if not candidates:
            raise ValueError(
                "Candidate Agent returned no valid locations."
                if get_language() == EN
                else "候选生成 Agent 没有返回有效地点。"
            )

        spatial_constraints = plan_spatial_constraints(evidence, cleaned_query)
        self._progress(progress, 55, tr("progress.gis"))
        gis_results, gis_backend = self.gis_verifier.verify(
            candidates, spatial_constraints, progress=progress
        )

        self._progress(progress, 82, tr("progress.agent3"))
        verification_payload = self.client.chat_json(
            VERIFY_SYSTEM_PROMPT,
            self._verify_user_prompt(
                cleaned_query, evidence, candidates, gis_results
            ),
            max_tokens=VERIFY_MAX_OUTPUT_TOKENS,
        )
        self._apply_verification(
            candidates,
            verification_payload,
            evidence,
            total_photo_count=len(paths),
        )
        candidates.sort(key=lambda item: item.ranking_score, reverse=True)

        self._progress(progress, 100, tr("progress.complete"))
        return GeoAnalysisResult(
            query=cleaned_query,
            image_path=paths[0] if paths else "",
            evidence_summary=evidence_summary,
            evidence=evidence,
            candidates=candidates,
            verification_summary=str(verification_payload.get("summary") or ""),
            caveat=str(
                verification_payload.get("caveat")
                or "结果已通过 OSM/PostGIS 核验，但尚未经过独立地理验证集校准。"
            ),
            model=self.client.model,
            image_paths=paths,
            case_mode=case_mode,
            gis_backend=gis_backend,
            spatial_constraints=spatial_constraints,
        )

    @staticmethod
    def _progress(
        callback: Optional[ProgressCallback], percent: int, message: str
    ) -> None:
        if callback:
            callback(percent, message)

    @staticmethod
    def _normalize_image_paths(
        image_path: str, image_paths: Optional[List[str]]
    ) -> List[str]:
        paths = list(image_paths or ())
        if image_path and image_path not in paths:
            paths.insert(0, image_path)
        cleaned = [str(Path(path)) for path in paths if str(path).strip()]
        return list(dict.fromkeys(cleaned))[:MAX_CASE_PHOTOS]

    @staticmethod
    def _evidence_user_prompt(
        query: str,
        local_evidence: List[Evidence],
        image_paths: List[str],
        case_mode: str,
        photo_ids: Optional[List[str]] = None,
    ) -> str:
        local = [
            {
                "id": shorten_text(item.evidence_id, 24),
                "kind": shorten_text(item.kind, 48),
                "value": shorten_text(item.value, 320),
                "reliability": item.reliability,
                "source": shorten_text(item.source, 80),
                "photo_ids": compact_text_list(
                    item.photo_ids, max_items=6, max_chars=12
                ),
            }
            for item in local_evidence[:20]
        ]
        language_instruction = (
            "Return human-readable text in English.\n"
            if get_language() == EN
            else "人类可读文本请使用中文。\n"
        )
        suffix = (
            "\nCase 模式："
            + shorten_text(case_mode, 32)
            + "\n照片编号："
            + compact_json(
                [
                    {
                        "photo_id": (
                            photo_ids[index - 1]
                            if photo_ids and index <= len(photo_ids)
                            else f"P{index}"
                        ),
                        "file": shorten_text(Path(path).name, 128),
                    }
                    for index, path in enumerate(image_paths, 1)
                ]
            )
            + "\n本机元数据（可能被篡改，仅作独立证据）："
            + compact_json(local)
        )
        return build_bounded_prompt(
            language_instruction + "用户查询：",
            query or "无，仅分析照片",
            suffix,
            EVIDENCE_PROMPT_CHAR_LIMIT,
        )

    @staticmethod
    def _select_case_evidence(
        evidence: List[Evidence],
        photo_ids: List[str],
        limit: int = 20,
    ) -> List[Evidence]:
        if len(evidence) <= limit:
            return evidence
        selected_ids = set()
        selected: List[Evidence] = []
        for photo_id in photo_ids:
            matches = sorted(
                (
                    item
                    for item in evidence
                    if photo_id in item.photo_ids
                ),
                key=lambda item: item.reliability,
                reverse=True,
            )
            for item in matches[:2]:
                if item.evidence_id not in selected_ids:
                    selected.append(item)
                    selected_ids.add(item.evidence_id)
        remaining = sorted(
            (
                item
                for item in evidence
                if item.evidence_id not in selected_ids
            ),
            key=lambda item: (
                item.source == "local-metadata",
                len(item.photo_ids),
                item.reliability,
            ),
            reverse=True,
        )
        selected.extend(remaining[: max(0, limit - len(selected))])
        order = {
            item.evidence_id: index
            for index, item in enumerate(evidence)
        }
        return sorted(
            selected[:limit],
            key=lambda item: order.get(item.evidence_id, len(order)),
        )

    @staticmethod
    def _candidate_user_prompt(
        query: str,
        evidence: List[Evidence],
        photo_count: int = 0,
        case_mode: str = "same_location",
    ) -> str:
        language_instruction = (
            "Return place names and explanations in English.\n"
            if get_language() == EN
            else "地点名称和解释请使用中文，可保留英文别名。\n"
        )
        evidence_payload = [
            GeoAgentPipeline._compact_evidence(item, verification=False)
            for item in evidence[:20]
        ]
        suffix = (
            f"\nCase 模式：{shorten_text(case_mode, 32)}；"
            f"照片数量：{max(0, min(photo_count, MAX_CASE_PHOTOS))}"
            + "\n证据："
            + compact_json(evidence_payload)
        )
        return build_bounded_prompt(
            language_instruction + "用户查询：",
            query or "无",
            suffix,
            CANDIDATE_PROMPT_CHAR_LIMIT,
        )

    @staticmethod
    def _verify_user_prompt(
        query: str,
        evidence: List[Evidence],
        candidates: List[Candidate],
        gis_results: Dict[str, CandidateGISResult],
    ) -> str:
        evidence_payload = [
            GeoAgentPipeline._compact_evidence(item, verification=True)
            for item in evidence[:20]
        ]
        candidate_payload = [
            {
                "id": item.candidate_id,
                "name": shorten_text(item.name, 96),
                "country": shorten_text(item.country, 64),
                "country_code": item.country_code,
                "region": shorten_text(item.region, 96),
                "latitude": item.latitude,
                "longitude": item.longitude,
                "initial_score": item.initial_score,
                "radius_km": item.radius_km,
                "supporting_evidence": compact_text_list(
                    item.supporting_evidence, max_items=12, max_chars=24
                ),
                "rationale": shorten_text(item.rationale, 200),
                "gis_verification": (
                    GeoAgentPipeline._compact_gis_result(
                        gis_results[item.candidate_id]
                    )
                    if item.candidate_id in gis_results
                    else {}
                ),
            }
            for item in candidates
        ]
        language_instruction = (
            "Return human-readable text in English.\n"
            if get_language() == EN
            else "人类可读文本请使用中文。\n"
        )
        suffix = (
            "\n证据："
            + compact_json(evidence_payload)
            + "\n候选："
            + compact_json(candidate_payload)
        )
        return build_bounded_prompt(
            language_instruction + "用户查询：",
            query or "无",
            suffix,
            VERIFY_PROMPT_CHAR_LIMIT,
        )

    @staticmethod
    def _compact_evidence(
        item: Evidence, verification: bool
    ) -> Dict[str, Any]:
        return {
            "id": shorten_text(item.evidence_id, 24),
            "kind": shorten_text(item.kind, 48),
            "value": shorten_text(item.value, 120 if verification else 320),
            "reliability": item.reliability,
            "scale": shorten_text(item.scale, 32),
            "photo_ids": compact_text_list(
                item.photo_ids, max_items=6, max_chars=12
            ),
            "correlation_group": shorten_text(
                item.correlation_group, 32 if verification else 96
            ),
            "supports": compact_text_list(
                item.supports,
                max_items=1 if verification else 4,
                max_chars=48 if verification else 96,
            ),
            "contradicts": compact_text_list(
                item.contradicts,
                max_items=1 if verification else 4,
                max_chars=48 if verification else 96,
            ),
        }

    @staticmethod
    def _compact_gis_result(
        result: CandidateGISResult,
    ) -> Dict[str, Any]:
        reverse = result.reverse
        ranked_checks = sorted(
            result.checks,
            key=lambda check: (
                not check.required,
                check.matched is not False,
                check.matched is None,
                -float(check.weight or 0.0),
            ),
        )[:3]
        return {
            "candidate_id": shorten_text(result.candidate_id, 24),
            "reverse": {
                "display_name": shorten_text(reverse.display_name, 160),
                "country": shorten_text(reverse.country, 64),
                "country_code": shorten_text(reverse.country_code, 8),
                "region": shorten_text(reverse.region, 96),
                "locality": shorten_text(reverse.locality, 96),
                "source": shorten_text(reverse.source, 48),
                "aliases": compact_text_list(
                    reverse.aliases, max_items=2, max_chars=64
                ),
            },
            "checks": [
                {
                    "check_id": shorten_text(check.check_id, 40),
                    "kind": shorten_text(check.kind, 32),
                    "label": shorten_text(check.label, 64),
                    "matched": check.matched,
                    "source": shorten_text(check.source, 48),
                    "count": check.count,
                    "nearest_distance_km": check.nearest_distance_km,
                    "detail": shorten_text(check.detail, 96),
                    "strength": check.strength,
                    "weight": check.weight,
                    "required": check.required,
                }
                for check in ranked_checks
            ],
            "gis_score": result.gis_score,
            "coverage": result.coverage,
            "verified": result.verified,
            "backend": shorten_text(result.backend, 96),
            "checks_total": len(result.checks),
            "checks_in_prompt": len(ranked_checks),
        }

    @staticmethod
    def _parse_evidence(
        payload: Dict[str, Any],
        local_evidence: List[Evidence],
        limit: int = 20,
    ) -> List[Evidence]:
        raw = payload.get("evidence")
        remote = [
            Evidence.from_dict(item, index + len(local_evidence))
            for index, item in enumerate(raw if isinstance(raw, list) else [])
            if isinstance(item, dict) and item.get("value")
        ]
        merged: List[Evidence] = []
        by_content: Dict[tuple, Evidence] = {}
        used_ids = set()
        for item in local_evidence + remote:
            normalized_value = " ".join(
                re.findall(r"[\w\u3400-\u9fff]+", item.value.casefold())
            )
            key = (item.kind.casefold(), normalized_value)
            existing = by_content.get(key)
            if existing is not None:
                existing.reliability = max(
                    existing.reliability, item.reliability
                )
                existing.supports = list(
                    dict.fromkeys(existing.supports + item.supports)
                )
                existing.contradicts = list(
                    dict.fromkeys(existing.contradicts + item.contradicts)
                )
                existing.photo_ids = list(
                    dict.fromkeys(existing.photo_ids + item.photo_ids)
                )
                if not existing.correlation_group:
                    existing.correlation_group = item.correlation_group
                continue
            if not item.evidence_id or item.evidence_id in used_ids:
                item.evidence_id = f"E{len(merged) + 1}"
                while item.evidence_id in used_ids:
                    item.evidence_id = f"E{len(merged) + len(used_ids) + 1}"
            used_ids.add(item.evidence_id)
            by_content[key] = item
            merged.append(item)
        return merged[: max(1, limit)]

    @staticmethod
    def _parse_candidates(payload: Dict[str, Any]) -> List[Candidate]:
        raw = payload.get("candidates")
        parsed = []
        for index, item in enumerate(raw if isinstance(raw, list) else []):
            if not isinstance(item, dict):
                continue
            try:
                parsed.append(Candidate.from_dict(item, index))
            except ValueError:
                continue
        return select_diverse_candidates(parsed, limit=8)

    @staticmethod
    def _apply_verification(
        candidates: List[Candidate],
        payload: Dict[str, Any],
        evidence: List[Evidence],
        total_photo_count: int = 0,
    ) -> None:
        raw = payload.get("candidates")
        verifications = {
            str(item.get("id")): item
            for item in (raw if isinstance(raw, list) else [])
            if isinstance(item, dict) and item.get("id")
        }
        for candidate in candidates:
            verification = verifications.get(candidate.candidate_id, {})
            adjusted = clamp(
                verification.get(
                    "evidence_score",
                    verification.get(
                        "adjusted_score", candidate.initial_score
                    ),
                )
            )
            candidate.model_verification_score = adjusted
            candidate.radius_km = clamp(
                verification.get("radius_km", candidate.radius_km),
                0.1,
                20000.0,
            )
            support = verification.get("supporting_evidence")
            if isinstance(support, list):
                candidate.supporting_evidence = [
                    str(item) for item in support if str(item).strip()
                ]
            contradictions = verification.get("contradictions")
            if isinstance(contradictions, list):
                candidate.contradictions = [
                    str(item) for item in contradictions if str(item).strip()
                ]
            if verification.get("rationale"):
                candidate.rationale = str(verification["rationale"])
            fuse_candidate_score(
                candidate,
                evidence,
                total_photo_count=total_photo_count,
            )
