"""Fuse live OSM or configured PostGIS evidence into candidate scores."""

from __future__ import annotations

import re
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from sakugis.agent_models import Candidate, clamp
from sakugis.gis_models import (
    CandidateGISResult,
    GISCheck,
    ReversePlace,
    SpatialConstraint,
)
from sakugis.i18n import EN, get_language, tr
from sakugis.osm_services import OSMServiceError, OSMServices
from sakugis.postgis_provider import PostGISError, PostGISProvider


ProgressCallback = Callable[[int, str], None]


class GISVerifier:
    def __init__(
        self,
        osm: Optional[OSMServices] = None,
        postgis: Optional[PostGISProvider] = None,
    ):
        self.osm = osm or OSMServices()
        self.postgis = postgis or PostGISProvider()

    def verify(
        self,
        candidates: Sequence[Candidate],
        constraints: Sequence[SpatialConstraint],
        progress: Optional[ProgressCallback] = None,
    ) -> Tuple[Dict[str, CandidateGISResult], str]:
        reverse: Dict[str, ReversePlace] = {}
        feature_checks: Dict[str, List[GISCheck]] = {
            candidate.candidate_id: [] for candidate in candidates
        }
        backend = "OSM Nominatim + Overpass"

        if self.postgis.enabled:
            try:
                reverse, feature_checks = self.postgis.verify(
                    candidates, constraints
                )
                backend = "PostGIS"
            except PostGISError:
                backend = "PostGIS unavailable; OSM fallback"

        if not reverse:
            for index, candidate in enumerate(candidates):
                if progress:
                    progress(
                        58 + int(10 * (index + 1) / max(1, len(candidates))),
                        tr("progress.reverse"),
                    )
                try:
                    reverse[candidate.candidate_id] = self.osm.reverse(
                        candidate.latitude,
                        candidate.longitude,
                        language=("en" if get_language() == EN else "zh-CN,en"),
                    )
                except OSMServiceError:
                    reverse[candidate.candidate_id] = ReversePlace()

        if not any(feature_checks.values()):
            online_candidates = list(candidates)[:5]
            online_constraints = [
                item for item in constraints if item.kind == "osm_tag"
            ][:4]
            try:
                queried_checks = self.osm.overpass_checks(
                    online_candidates, online_constraints
                )
                feature_checks = {}
                queried_candidate_ids = {
                    candidate.candidate_id for candidate in online_candidates
                }
                queried_constraint_ids = {
                    constraint.constraint_id for constraint in online_constraints
                }
                for candidate in candidates:
                    candidate_checks = list(
                        queried_checks.get(candidate.candidate_id, [])
                    )
                    for constraint in constraints:
                        if constraint.kind != "osm_tag":
                            continue
                        if (
                            candidate.candidate_id not in queried_candidate_ids
                            or constraint.constraint_id not in queried_constraint_ids
                        ):
                            candidate_checks.append(
                                GISCheck(
                                    check_id=constraint.constraint_id,
                                    kind="spatial_constraint",
                                    label=constraint.label,
                                    matched=None,
                                    source="OSM public-query limit",
                                    weight=constraint.importance,
                                    required=constraint.required,
                                )
                            )
                    feature_checks[candidate.candidate_id] = candidate_checks
            except OSMServiceError:
                feature_checks = {
                    candidate.candidate_id: [
                        GISCheck(
                            check_id=constraint.constraint_id,
                            kind="spatial_constraint",
                            label=constraint.label,
                            matched=None,
                            source="OSM Overpass unavailable",
                            weight=constraint.importance,
                            required=constraint.required,
                        )
                        for constraint in constraints
                        if constraint.kind == "osm_tag"
                    ]
                    for candidate in candidates
                }

        results: Dict[str, CandidateGISResult] = {}
        for candidate in candidates:
            place = reverse.get(candidate.candidate_id, ReversePlace())
            checks = list(feature_checks.get(candidate.candidate_id, []))
            checks.insert(0, self._locality_check(candidate, place))
            checks.insert(0, self._country_check(candidate, place))
            if any(item.kind == "driving_side" for item in constraints):
                driving_constraint = next(
                    item
                    for item in constraints
                    if item.kind == "driving_side"
                )
                checks.append(
                    self.osm.driving_side_check(
                        candidate.candidate_id,
                        place.country_code or candidate.country_code,
                        weight=driving_constraint.importance,
                        required=driving_constraint.required,
                    )
                )
            score = self._score(checks)
            coverage = self._coverage(checks)
            result = CandidateGISResult(
                candidate_id=candidate.candidate_id,
                reverse=place,
                checks=checks,
                gis_score=score,
                coverage=coverage,
                verified=any(check.matched is not None for check in checks),
                backend=backend,
            )
            results[candidate.candidate_id] = result
            candidate.gis_score = score
            candidate.gis_coverage = coverage
            candidate.gis_verified = result.verified
            candidate.reverse_label = place.display_name
            candidate.gis_backend = backend
            candidate.gis_checks = checks
        return results, backend

    @staticmethod
    def _country_check(candidate: Candidate, place: ReversePlace) -> GISCheck:
        expected_code = candidate.country_code.casefold()
        actual_code = place.country_code.casefold()
        strength: Optional[float] = None
        if expected_code and actual_code:
            matched: Optional[bool] = expected_code == actual_code
            strength = 1.0 if matched else 0.0
        elif candidate.country and place.country:
            strength = _text_similarity(candidate.country, place.country)
            matched = strength >= 0.4
        else:
            matched = None
        return GISCheck(
            check_id="reverse_country",
            kind="reverse_geocode",
            label="reverse-geocoded country",
            matched=matched,
            source=place.source or "reverse geocoder unavailable",
            detail=(
                f"{place.country} ({place.country_code})"
                if place.country or place.country_code
                else ""
            ),
            strength=strength,
        )

    @staticmethod
    def _locality_check(candidate: Candidate, place: ReversePlace) -> GISCheck:
        candidate_label = " ".join([candidate.name, candidate.region])
        actual_label = " ".join(
            [place.locality, place.region, place.display_name] + place.aliases
        )
        similarity = _text_similarity(candidate_label, actual_label)
        matched: Optional[bool] = similarity >= 0.2 if actual_label.strip() else None
        return GISCheck(
            check_id="reverse_locality",
            kind="reverse_geocode",
            label="reverse-geocoded locality",
            matched=matched,
            source=place.source or "reverse geocoder unavailable",
            detail=place.locality or place.region or place.display_name,
            strength=similarity if actual_label.strip() else None,
        )

    @staticmethod
    def _score(checks: Sequence[GISCheck]) -> float:
        if not checks:
            return 0.5
        weights = GISVerifier._normalized_weights(checks)
        weighted_score = 0.0
        available_weight = 0.0
        country_mismatch = False
        for index, check in enumerate(checks):
            weight = weights[index]
            if check.matched is None:
                continue
            value = GISVerifier._check_strength(check)
            weighted_score += weight * value
            available_weight += weight
            if check.check_id == "reverse_country" and check.matched is False:
                country_mismatch = True
        if available_weight <= 0.0:
            return 0.5
        score = weighted_score / available_weight
        if country_mismatch:
            score *= 0.20
        return clamp(score)

    @staticmethod
    def _coverage(checks: Sequence[GISCheck]) -> float:
        if not checks:
            return 0.0
        weights = GISVerifier._normalized_weights(checks)
        total = sum(weights)
        available = 0.0
        for index, check in enumerate(checks):
            if check.matched is not None:
                available += weights[index]
        return clamp(available / max(total, 0.0001))

    @staticmethod
    def _normalized_weights(checks: Sequence[GISCheck]) -> List[float]:
        constraint_indices = [
            index
            for index, check in enumerate(checks)
            if check.check_id
            not in {"reverse_country", "reverse_locality"}
        ]
        importance_total = sum(
            max(0.05, checks[index].weight)
            for index in constraint_indices
        )
        has_constraints = bool(constraint_indices)
        country_weight = 0.18 if has_constraints else 0.67
        locality_weight = 0.07 if has_constraints else 0.33
        constraint_pool = 0.75 if has_constraints else 0.0
        weights: List[float] = []
        for index, check in enumerate(checks):
            if check.check_id == "reverse_country":
                weights.append(country_weight)
            elif check.check_id == "reverse_locality":
                weights.append(locality_weight)
            elif importance_total > 0:
                weights.append(
                    constraint_pool
                    * max(0.05, check.weight)
                    / importance_total
                )
            else:
                weights.append(0.0)
        return weights

    @staticmethod
    def _check_strength(check: GISCheck) -> float:
        if check.strength is not None:
            return clamp(check.strength)
        if check.matched is True:
            return 1.0
        if check.kind == "spatial_constraint" and check.source.startswith(
            "OSM"
        ):
            return 0.25
        if check.check_id == "reverse_locality":
            return 0.20
        return 0.0


def _text_similarity(first: str, second: str) -> float:
    first_tokens = set(re.findall(r"[\w\u3400-\u9fff]+", first.casefold()))
    second_tokens = set(re.findall(r"[\w\u3400-\u9fff]+", second.casefold()))
    if not first_tokens or not second_tokens:
        return 0.0
    intersection = first_tokens & second_tokens
    return len(intersection) / max(1, min(len(first_tokens), len(second_tokens)))
