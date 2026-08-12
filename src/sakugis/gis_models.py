"""Data structures for deterministic GIS verification."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class SpatialConstraint:
    constraint_id: str
    kind: str
    label: str
    radius_km: float
    tag_key: str = ""
    tag_value: str = ""
    evidence_ids: List[str] = field(default_factory=list)
    importance: float = 1.0
    required: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "SpatialConstraint":
        return cls(
            constraint_id=str(value.get("constraint_id") or value.get("id") or ""),
            kind=str(value.get("kind") or "unknown"),
            label=str(value.get("label") or ""),
            radius_km=float(value.get("radius_km") or 0.0),
            tag_key=str(value.get("tag_key") or ""),
            tag_value=str(value.get("tag_value") or ""),
            evidence_ids=[
                str(item)
                for item in value.get("evidence_ids", [])
                if str(item).strip()
            ],
            importance=float(value.get("importance", 1.0)),
            required=bool(value.get("required", False)),
        )


@dataclass
class GISCheck:
    check_id: str
    kind: str
    label: str
    matched: Optional[bool]
    source: str
    count: int = 0
    nearest_distance_km: Optional[float] = None
    detail: str = ""
    strength: Optional[float] = None
    weight: float = 1.0
    required: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "GISCheck":
        matched = value.get("matched")
        if matched not in (True, False):
            matched = None
        nearest = value.get("nearest_distance_km")
        strength = value.get("strength")
        return cls(
            check_id=str(value.get("check_id") or value.get("id") or ""),
            kind=str(value.get("kind") or "unknown"),
            label=str(value.get("label") or ""),
            matched=matched,
            source=str(value.get("source") or ""),
            count=int(value.get("count") or 0),
            nearest_distance_km=(float(nearest) if nearest is not None else None),
            detail=str(value.get("detail") or ""),
            strength=float(strength) if strength is not None else None,
            weight=float(value.get("weight", 1.0)),
            required=bool(value.get("required", False)),
        )


@dataclass
class ReversePlace:
    display_name: str = ""
    country: str = ""
    country_code: str = ""
    region: str = ""
    locality: str = ""
    source: str = ""
    aliases: List[str] = field(default_factory=list)


@dataclass
class CandidateGISResult:
    candidate_id: str
    reverse: ReversePlace = field(default_factory=ReversePlace)
    checks: List[GISCheck] = field(default_factory=list)
    gis_score: float = 0.0
    coverage: float = 0.0
    verified: bool = False
    backend: str = ""

    def to_prompt_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "reverse": asdict(self.reverse),
            "checks": [check.to_dict() for check in self.checks],
            "gis_score": self.gis_score,
            "coverage": self.coverage,
            "verified": self.verified,
            "backend": self.backend,
        }
