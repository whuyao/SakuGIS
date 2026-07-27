"""Convert multimodal evidence into bounded, auditable GIS constraints."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence, Tuple

from sakugis.agent_models import Evidence
from sakugis.gis_models import SpatialConstraint


@dataclass(frozen=True)
class ConstraintRule:
    constraint_id: str
    label: str
    phrases: Tuple[str, ...]
    tag_key: str
    tag_value: str
    radius_km: float


OSM_RULES: Sequence[ConstraintRule] = (
    ConstraintRule(
        "coastline",
        "coastline",
        ("临海", "海岸", "海边", "coast", "coastal", "seaside", "ocean"),
        "natural",
        "coastline",
        30.0,
    ),
    ConstraintRule(
        "volcano",
        "volcano",
        ("火山", "volcano", "volcanic"),
        "natural",
        "volcano",
        100.0,
    ),
    ConstraintRule(
        "vineyard",
        "vineyard",
        ("葡萄园", "葡萄酒产区", "vineyard", "winery", "wine region"),
        "landuse",
        "vineyard",
        60.0,
    ),
    ConstraintRule(
        "peak",
        "mountain peak",
        ("山峰", "高山", "mountain", "peak"),
        "natural",
        "peak",
        60.0,
    ),
    ConstraintRule(
        "river",
        "river",
        ("河流", "河边", "river", "riverside"),
        "waterway",
        "river",
        25.0,
    ),
    ConstraintRule(
        "railway_station",
        "railway station",
        ("火车站", "铁路站", "railway station", "train station"),
        "railway",
        "station",
        20.0,
    ),
    ConstraintRule(
        "airport",
        "airport",
        ("机场", "airport", "aerodrome"),
        "aeroway",
        "aerodrome",
        40.0,
    ),
    ConstraintRule(
        "university",
        "university",
        ("大学", "校园", "university", "campus"),
        "amenity",
        "university",
        20.0,
    ),
)

DRIVING_SIDE_PHRASES = (
    "左侧通行",
    "靠左行驶",
    "left-hand traffic",
    "left hand traffic",
    "drive on the left",
)


def _contains_any(text: str, phrases: Iterable[str]) -> bool:
    lowered = text.casefold()
    return any(phrase.casefold() in lowered for phrase in phrases)


def plan_spatial_constraints(
    evidence: List[Evidence], query: str, maximum: int = 6
) -> List[SpatialConstraint]:
    combined = "\n".join([query] + [item.value for item in evidence])
    constraints: List[SpatialConstraint] = []
    for rule in OSM_RULES:
        if not _contains_any(combined, rule.phrases):
            continue
        related = [
            item.evidence_id
            for item in evidence
            if _contains_any(item.value, rule.phrases)
        ]
        importance = _constraint_importance(
            evidence, related, _contains_any(query, rule.phrases)
        )
        constraints.append(
            SpatialConstraint(
                constraint_id=rule.constraint_id,
                kind="osm_tag",
                label=rule.label,
                radius_km=rule.radius_km,
                tag_key=rule.tag_key,
                tag_value=rule.tag_value,
                evidence_ids=related,
                importance=importance,
                required=_contains_any(query, rule.phrases),
            )
        )
    if _contains_any(combined, DRIVING_SIDE_PHRASES):
        related = [
            item.evidence_id
            for item in evidence
            if _contains_any(item.value, DRIVING_SIDE_PHRASES)
        ]
        constraints.append(
            SpatialConstraint(
                constraint_id="left_hand_traffic",
                kind="driving_side",
                label="left-hand traffic",
                radius_km=0.0,
                evidence_ids=related,
                importance=_constraint_importance(
                    evidence,
                    related,
                    _contains_any(query, DRIVING_SIDE_PHRASES),
                ),
                required=_contains_any(query, DRIVING_SIDE_PHRASES),
            )
        )
    return constraints[:maximum]


def _constraint_importance(
    evidence: List[Evidence], evidence_ids: List[str], explicit_query: bool
) -> float:
    if explicit_query:
        return 1.0
    related = {
        item.evidence_id: item.reliability for item in evidence
    }
    return max(
        0.25,
        min(1.0, max((related.get(item, 0.0) for item in evidence_ids), default=0.0)),
    )
