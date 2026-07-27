"""Three-stage Qwen-assisted geolocation pipeline."""

from __future__ import annotations

import json
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
from sakugis.qwen_client import QwenClient
from sakugis.ranking import fuse_candidate_score, select_diverse_candidates
from sakugis.spatial_constraints import plan_spatial_constraints


ProgressCallback = Callable[[int, str], None]


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
reliability 只表示该证据识别是否可靠，不是地点概率。输入包含多张照片时，
必须用 P1、P2… 标出每条证据来自哪些照片；同一物体在多张照片中出现时合并
为一条证据，并列出全部 photo_ids，避免重复计分。
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
        evidence_payload = self.client.chat_json(
            EVIDENCE_SYSTEM_PROMPT,
            self._evidence_user_prompt(
                cleaned_query,
                local_evidence,
                paths,
                case_mode,
            ),
            image_paths=paths,
        )
        evidence = self._parse_evidence(evidence_payload, local_evidence)

        self._progress(progress, 42, tr("progress.agent2"))
        candidate_payload = self.client.chat_json(
            CANDIDATE_SYSTEM_PROMPT,
            self._candidate_user_prompt(
                cleaned_query,
                evidence,
                photo_count=len(paths),
                case_mode=case_mode,
            ),
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
            evidence_summary=str(evidence_payload.get("summary") or ""),
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
    ) -> str:
        local = [
            {
                "id": item.evidence_id,
                "kind": item.kind,
                "value": item.value,
                "reliability": item.reliability,
                "source": item.source,
                "photo_ids": item.photo_ids,
            }
            for item in local_evidence
        ]
        language_instruction = (
            "Return human-readable text in English.\n"
            if get_language() == EN
            else "人类可读文本请使用中文。\n"
        )
        return (
            language_instruction
            +
            "用户查询："
            + (query or "无，仅分析照片")
            + "\nCase 模式："
            + case_mode
            + "\n照片编号："
            + json.dumps(
                [
                    {"photo_id": f"P{index}", "file": Path(path).name}
                    for index, path in enumerate(image_paths, 1)
                ],
                ensure_ascii=False,
            )
            + "\n本机读取到的元数据（可能被篡改，只作独立证据）："
            + json.dumps(local, ensure_ascii=False)
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
        return (
            language_instruction
            +
            "用户查询："
            + (query or "无")
            + f"\nCase 模式：{case_mode}；照片数量：{photo_count}"
            + "\n证据："
            + json.dumps(
                [
                    {
                        "id": item.evidence_id,
                        "kind": item.kind,
                        "value": item.value,
                        "reliability": item.reliability,
                        "scale": item.scale,
                        "photo_ids": item.photo_ids,
                        "correlation_group": item.correlation_group,
                        "supports": item.supports,
                        "contradicts": item.contradicts,
                    }
                    for item in evidence
                ],
                ensure_ascii=False,
            )
        )

    @staticmethod
    def _verify_user_prompt(
        query: str,
        evidence: List[Evidence],
        candidates: List[Candidate],
        gis_results: Dict[str, CandidateGISResult],
    ) -> str:
        evidence_payload = [
            {
                "id": item.evidence_id,
                "kind": item.kind,
                "value": item.value,
                "reliability": item.reliability,
                "photo_ids": item.photo_ids,
                "correlation_group": item.correlation_group,
                "supports": item.supports,
                "contradicts": item.contradicts,
            }
            for item in evidence
        ]
        candidate_payload = [
            {
                "id": item.candidate_id,
                "name": item.name,
                "country": item.country,
                "country_code": item.country_code,
                "region": item.region,
                "latitude": item.latitude,
                "longitude": item.longitude,
                "initial_score": item.initial_score,
                "radius_km": item.radius_km,
                "supporting_evidence": item.supporting_evidence,
                "rationale": item.rationale,
                "gis_verification": (
                    gis_results[item.candidate_id].to_prompt_dict()
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
        return (
            language_instruction
            +
            "用户查询："
            + (query or "无")
            + "\n证据："
            + json.dumps(evidence_payload, ensure_ascii=False)
            + "\n候选："
            + json.dumps(candidate_payload, ensure_ascii=False)
        )

    @staticmethod
    def _parse_evidence(
        payload: Dict[str, Any], local_evidence: List[Evidence]
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
        return merged[:20]

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
