"""Structured data exchanged by SakuGIS geolocation agents."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List

from sakugis.gis_models import GISCheck, SpatialConstraint


def clamp(value: Any, minimum: float = 0.0, maximum: float = 1.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return minimum
    return max(minimum, min(maximum, number))


def clean_string_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


@dataclass
class Evidence:
    evidence_id: str
    kind: str
    value: str
    reliability: float
    source: str
    scale: str = "unknown"
    supports: List[str] = field(default_factory=list)
    contradicts: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, value: Dict[str, Any], index: int) -> "Evidence":
        return cls(
            evidence_id=str(value.get("id") or f"E{index + 1}"),
            kind=str(value.get("kind") or "unknown"),
            value=str(value.get("value") or ""),
            reliability=clamp(value.get("reliability")),
            source=str(value.get("source") or "qwen"),
            scale=str(value.get("scale") or "unknown"),
            supports=clean_string_list(value.get("supports")),
            contradicts=clean_string_list(value.get("contradicts")),
        )


@dataclass
class Candidate:
    candidate_id: str
    name: str
    country: str
    region: str
    latitude: float
    longitude: float
    initial_score: float
    ranking_score: float
    radius_km: float
    country_code: str = ""
    model_verification_score: float = 0.0
    gis_score: float = 0.0
    gis_coverage: float = 0.0
    gis_verified: bool = False
    reverse_label: str = ""
    gis_backend: str = ""
    gis_checks: List[GISCheck] = field(default_factory=list)
    ranking_components: Dict[str, float] = field(default_factory=dict)
    supporting_evidence: List[str] = field(default_factory=list)
    contradictions: List[str] = field(default_factory=list)
    rationale: str = ""

    @classmethod
    def from_dict(cls, value: Dict[str, Any], index: int) -> "Candidate":
        try:
            latitude = float(value["latitude"])
            longitude = float(value["longitude"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("候选位置缺少有效经纬度。") from exc
        if not -90.0 <= latitude <= 90.0 or not -180.0 <= longitude <= 180.0:
            raise ValueError("候选位置的经纬度超出范围。")
        initial = clamp(value.get("initial_score"))
        radius = clamp(value.get("radius_km", 250.0), 0.1, 20000.0)
        return cls(
            candidate_id=str(value.get("id") or f"C{index + 1}"),
            name=str(value.get("name") or f"候选 {index + 1}"),
            country=str(value.get("country") or ""),
            region=str(value.get("region") or ""),
            latitude=latitude,
            longitude=longitude,
            initial_score=initial,
            ranking_score=initial,
            radius_km=radius,
            country_code=str(value.get("country_code") or "").upper()[:2],
            supporting_evidence=clean_string_list(
                value.get("supporting_evidence") or value.get("evidence_ids")
            ),
            contradictions=clean_string_list(value.get("contradictions")),
            rationale=str(value.get("rationale") or ""),
        )


@dataclass
class GeoAnalysisResult:
    query: str
    image_path: str
    evidence_summary: str
    evidence: List[Evidence]
    candidates: List[Candidate]
    verification_summary: str
    caveat: str
    model: str
    confidence_status: str = "uncalibrated"
    gis_backend: str = ""
    spatial_constraints: List[SpatialConstraint] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
