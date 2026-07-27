"""Deterministic uncertainty-aware candidate selection and score fusion."""

from __future__ import annotations

import math
import re
from typing import Iterable, List, Sequence

from sakugis.agent_models import Candidate, Evidence, clamp


_SCALE_CONFIDENCE = {
    "point": 0.95,
    "city": 0.85,
    "region": 0.72,
    "country": 0.65,
    "global": 0.25,
    "context": 0.30,
    "unknown": 0.35,
}
_SOURCE_CONFIDENCE = {
    "local-metadata": 0.95,
    "user-query": 1.0,
    "vision": 0.85,
    "ocr": 0.80,
    "qwen": 0.72,
}


def haversine_km(
    latitude_a: float,
    longitude_a: float,
    latitude_b: float,
    longitude_b: float,
) -> float:
    earth_radius_km = 6371.0088
    lat_a = math.radians(latitude_a)
    lat_b = math.radians(latitude_b)
    delta_lat = lat_b - lat_a
    delta_lon = math.radians(
        ((longitude_b - longitude_a + 180.0) % 360.0) - 180.0
    )
    value = (
        math.sin(delta_lat / 2.0) ** 2
        + math.cos(lat_a) * math.cos(lat_b) * math.sin(delta_lon / 2.0) ** 2
    )
    return earth_radius_km * 2.0 * math.asin(
        min(1.0, math.sqrt(max(0.0, value)))
    )


def evidence_confidence(
    evidence: Sequence[Evidence], evidence_ids: Iterable[str] = ()
) -> float:
    """Combine independent clues without treating model scores as probabilities."""

    requested = {str(item) for item in evidence_ids if str(item).strip()}
    selected = [
        item for item in evidence if not requested or item.evidence_id in requested
    ]
    if requested and not selected:
        selected = list(evidence)
    remaining_uncertainty = 1.0
    for item in selected:
        scale = _SCALE_CONFIDENCE.get(
            item.scale.casefold(), _SCALE_CONFIDENCE["unknown"]
        )
        source = _SOURCE_CONFIDENCE.get(item.source.casefold(), 0.70)
        contribution = clamp(item.reliability * scale * source, 0.0, 0.95)
        remaining_uncertainty *= 1.0 - contribution
    return clamp(1.0 - remaining_uncertainty, 0.0, 0.95)


def fuse_candidate_score(
    candidate: Candidate,
    evidence: Sequence[Evidence],
    total_photo_count: int = 0,
) -> float:
    """Fuse two model stages with GIS while shrinking low-coverage signals."""

    confidence = evidence_confidence(
        evidence, candidate.supporting_evidence
    )
    model_score = clamp(candidate.model_verification_score)
    effective_model = 0.5 + confidence * (model_score - 0.5)
    effective_gis = (
        0.5
        + candidate.gis_coverage * (candidate.gis_score - 0.5)
        if candidate.gis_verified
        else 0.5
    )
    contradiction_penalty = min(
        0.10, 0.025 * len(candidate.contradictions)
    ) * max(0.35, confidence)
    supported_evidence_ids = set(candidate.supporting_evidence)
    supported_photo_ids = {
        photo_id
        for item in evidence
        if item.evidence_id in supported_evidence_ids
        for photo_id in item.photo_ids
    }
    candidate.photo_total_count = max(0, int(total_photo_count))
    candidate.photo_support_count = len(supported_photo_ids)
    if candidate.photo_total_count <= 1:
        candidate.photo_consistency = 1.0
        effective_photo_consistency = 1.0
        score = (
            0.20 * candidate.initial_score
            + 0.35 * effective_model
            + 0.45 * effective_gis
            - contradiction_penalty
        )
    else:
        candidate.photo_consistency = clamp(
            candidate.photo_support_count / candidate.photo_total_count
        )
        effective_photo_consistency = (
            0.5 + confidence * (candidate.photo_consistency - 0.5)
        )
        score = (
            0.18 * candidate.initial_score
            + 0.30 * effective_model
            + 0.10 * effective_photo_consistency
            + 0.42 * effective_gis
            - contradiction_penalty
        )

    country_mismatch = any(
        check.check_id == "reverse_country" and check.matched is False
        for check in candidate.gis_checks
    )
    driving_mismatch = any(
        check.check_id == "left_hand_traffic" and check.matched is False
        for check in candidate.gis_checks
    )
    required_spatial_mismatches = sum(
        1
        for check in candidate.gis_checks
        if check.required
        and check.kind == "spatial_constraint"
        and check.matched is False
    )
    required_unknowns = sum(
        1
        for check in candidate.gis_checks
        if check.required and check.matched is None
    )
    if country_mismatch:
        score = min(score, 0.18)
    elif driving_mismatch:
        score = min(score, 0.42)
    elif required_spatial_mismatches:
        score = min(
            score,
            max(0.35, 0.50 - 0.08 * (required_spatial_mismatches - 1)),
        )
    if required_unknowns:
        score = min(score, max(0.55, 0.95 - 0.10 * required_unknowns))

    candidate.ranking_components = {
        "retrieval": clamp(candidate.initial_score),
        "model": model_score,
        "evidence_confidence": confidence,
        "effective_model": clamp(effective_model),
        "gis": clamp(candidate.gis_score),
        "gis_coverage": clamp(candidate.gis_coverage),
        "effective_gis": clamp(effective_gis),
        "photo_consistency": candidate.photo_consistency,
        "effective_photo_consistency": effective_photo_consistency,
        "photo_support_count": float(candidate.photo_support_count),
        "photo_total_count": float(candidate.photo_total_count),
        "contradiction_penalty": contradiction_penalty,
        "required_mismatches": float(required_spatial_mismatches),
        "required_unknowns": float(required_unknowns),
    }
    candidate.ranking_score = clamp(score)
    candidate.ranking_components["final"] = candidate.ranking_score
    return candidate.ranking_score


def select_diverse_candidates(
    candidates: Sequence[Candidate],
    limit: int = 8,
    duplicate_distance_km: float = 20.0,
) -> List[Candidate]:
    """Remove metro-scale duplicates, then retain globally distinct hypotheses."""

    ordered = sorted(
        candidates, key=lambda item: item.initial_score, reverse=True
    )
    deduplicated: List[Candidate] = []
    for candidate in ordered:
        name_key = _place_key(candidate)
        duplicate = False
        for existing in deduplicated:
            same_place_name = bool(name_key) and name_key == _place_key(existing)
            very_close = (
                haversine_km(
                    candidate.latitude,
                    candidate.longitude,
                    existing.latitude,
                    existing.longitude,
                )
                < duplicate_distance_km
            )
            if same_place_name or very_close:
                duplicate = True
                break
        if not duplicate:
            deduplicated.append(candidate)

    selected: List[Candidate] = []
    remaining = list(deduplicated)
    while remaining and len(selected) < max(1, limit):
        if not selected:
            best = remaining[0]
        else:
            best = max(
                remaining,
                key=lambda item: (
                    0.85 * item.initial_score
                    + 0.15
                    * min(
                        1.0,
                        min(
                            haversine_km(
                                item.latitude,
                                item.longitude,
                                chosen.latitude,
                                chosen.longitude,
                            )
                            for chosen in selected
                        )
                        / 1500.0,
                    ),
                    item.initial_score,
                ),
            )
        selected.append(best)
        remaining.remove(best)

    selected.sort(key=lambda item: item.initial_score, reverse=True)
    for index, candidate in enumerate(selected, 1):
        candidate.candidate_id = f"C{index}"
    return selected


def _place_key(candidate: Candidate) -> str:
    tokens = re.findall(
        r"[\w\u3400-\u9fff]+",
        " ".join(
            [candidate.name, candidate.region, candidate.country]
        ).casefold(),
    )
    return "|".join(tokens)
