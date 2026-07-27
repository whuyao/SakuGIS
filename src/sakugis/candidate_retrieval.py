"""Resolve Agent 2 hypotheses against real OSM/PostGIS place records."""

from __future__ import annotations

import difflib
import re
from typing import Callable, List, Optional, Sequence, Tuple

from sakugis.agent_models import Candidate, RetrievedPlace, clamp
from sakugis.i18n import EN, get_language
from sakugis.osm_services import OSMServiceError, OSMServices
from sakugis.postgis_provider import PostGISError, PostGISProvider
from sakugis.ranking import haversine_km, select_diverse_candidates


RetrievalProgress = Callable[[int, int], None]


class HybridCandidateRetriever:
    """Use a configured local OSM index first, then policy-aware Nominatim."""

    def __init__(
        self,
        osm: Optional[OSMServices] = None,
        postgis: Optional[PostGISProvider] = None,
        maximum_queries: int = 8,
    ):
        self.osm = osm or OSMServices()
        self.postgis = postgis or PostGISProvider()
        self.maximum_queries = max(1, min(12, int(maximum_queries)))

    def resolve(
        self,
        candidates: Sequence[Candidate],
        progress: Optional[RetrievalProgress] = None,
    ) -> Tuple[List[Candidate], str, int]:
        working = list(candidates)[: self.maximum_queries]
        if not working:
            return [], "no candidate hypotheses", 0

        queried_backends = set()
        resolved_count = 0
        for index, candidate in enumerate(working, 1):
            if progress:
                progress(index, len(working))
            hits: List[RetrievedPlace] = []
            candidate_query_available = False
            if self.postgis.enabled:
                try:
                    postgis_query = self._postgis_query(candidate)
                    candidate.retrieval_query = postgis_query
                    hits.extend(
                        self.postgis.search_places(
                            postgis_query, limit=3
                        )
                    )
                    queried_backends.add("PostGIS OSM index")
                    candidate_query_available = True
                except PostGISError:
                    pass
            postgis_best = max(
                (
                    self._score_hit(candidate, hit)
                    for hit in hits
                ),
                default=0.0,
            )
            if not hits or postgis_best < 0.40:
                for query_text in self._queries(candidate)[:2]:
                    try:
                        candidate.retrieval_query = query_text
                        online_hits = self.osm.search_places(
                            query_text,
                            language=(
                                "en"
                                if get_language() == EN
                                else "zh-CN,en"
                            ),
                            limit=3,
                        )
                        hits.extend(online_hits)
                        queried_backends.add("OSM Nominatim")
                        candidate_query_available = True
                        if online_hits:
                            break
                    except OSMServiceError:
                        break

            best_lookup_score = max(
                (
                    self._score_hit(candidate, hit)
                    for hit in hits
                ),
                default=0.0,
            )
            if best_lookup_score < 0.35 and candidate_query_available:
                reverse_lookup = getattr(
                    self.osm, "reverse_place_record", None
                )
                if callable(reverse_lookup):
                    try:
                        reverse_hit = reverse_lookup(
                            candidate.model_latitude,
                            candidate.model_longitude,
                            language=(
                                "en"
                                if get_language() == EN
                                else "zh-CN,en"
                            ),
                        )
                        if reverse_hit is not None:
                            hits.append(reverse_hit)
                            queried_backends.add("OSM Nominatim reverse")
                    except OSMServiceError:
                        pass

            if not hits:
                candidate.retrieval_source = (
                    "place index: no match"
                    if candidate_query_available
                    else "model fallback"
                )
                candidate.retrieval_verified = False
                candidate.retrieval_score = (
                    candidate.model_candidate_score * 0.65
                    if candidate_query_available
                    else candidate.model_candidate_score
                )
                candidate.initial_score = candidate.retrieval_score
                continue

            best_hit, best_score = max(
                (
                    (hit, self._score_hit(candidate, hit))
                    for hit in hits
                ),
                key=lambda item: item[1],
            )
            if best_score < 0.35:
                candidate.retrieval_source = "place index: low similarity"
                candidate.retrieval_verified = False
                candidate.retrieval_score = (
                    candidate.model_candidate_score * 0.65
                )
                candidate.initial_score = candidate.retrieval_score
                continue
            self._apply_hit(candidate, best_hit, best_score)
            resolved_count += 1

        backend = " + ".join(sorted(queried_backends))
        if not backend:
            backend = "place lookup unavailable; model fallback"
        elif resolved_count < len(working):
            backend += " + unresolved model hypotheses"
        selected = select_diverse_candidates(working, limit=8)
        return (
            selected,
            backend,
            sum(
                1
                for candidate in selected
                if candidate.retrieval_verified
            ),
        )

    @staticmethod
    def _queries(candidate: Candidate) -> List[str]:
        aliases = HybridCandidateRetriever._name_aliases(candidate.name)
        queries = []
        english_alias = next(
            (alias for alias in aliases if re.search(r"[A-Za-z]", alias)),
            "",
        )
        if english_alias:
            queries.append(english_alias)
        if candidate.retrieval_query:
            queries.append(candidate.retrieval_query)
        queries.append(
            ", ".join(
                part
                for part in (
                    candidate.name,
                    candidate.region,
                    candidate.country,
                )
                if part
            )
        )
        queries.extend(aliases)
        return list(
            dict.fromkeys(
                " ".join(query.split())[:320]
                for query in queries
                if query.strip()
            )
        )

    @staticmethod
    def _postgis_query(candidate: Candidate) -> str:
        aliases = HybridCandidateRetriever._name_aliases(candidate.name)
        english_alias = next(
            (alias for alias in aliases if re.search(r"[A-Za-z]", alias)),
            "",
        )
        return english_alias or (aliases[0] if aliases else candidate.name)

    @staticmethod
    def _name_aliases(name: str) -> List[str]:
        text = " ".join(str(name or "").split())
        aliases = [
            match.strip()
            for match in re.findall(r"[\(（]([^\)）]+)[\)）]", text)
            if match.strip()
        ]
        without_parentheses = re.sub(
            r"\s*[\(（][^\)）]+[\)）]\s*", " ", text
        ).strip()
        if without_parentheses:
            aliases.append(without_parentheses)
        if text:
            aliases.append(text)
        return list(dict.fromkeys(aliases))

    @staticmethod
    def _apply_hit(
        candidate: Candidate, hit: RetrievedPlace, retrieval_score: float
    ) -> None:
        candidate.latitude = hit.latitude
        candidate.longitude = hit.longitude
        candidate.retrieval_verified = True
        candidate.retrieval_score = clamp(retrieval_score)
        candidate.retrieval_source = hit.source
        candidate.retrieval_source_id = hit.source_id
        candidate.retrieval_label = hit.display_name
        candidate.initial_score = clamp(
            0.55 * candidate.model_candidate_score
            + 0.45 * candidate.retrieval_score
        )
        if not candidate.country and hit.country:
            candidate.country = hit.country
        if not candidate.country_code and hit.country_code:
            candidate.country_code = hit.country_code
        if not candidate.region and hit.region:
            candidate.region = hit.region

    @staticmethod
    def _score_hit(candidate: Candidate, hit: RetrievedPlace) -> float:
        name_similarity = max(
            _text_similarity(candidate.name, hit.name),
            _text_similarity(candidate.name, hit.display_name),
            _text_similarity(candidate.retrieval_query, hit.display_name),
        )
        context_similarity = max(
            _text_similarity(candidate.region, hit.region),
            _text_similarity(candidate.country, hit.country),
            _text_similarity(
                " ".join([candidate.region, candidate.country]),
                hit.display_name,
            ),
        )
        expected_code = candidate.country_code.casefold()
        actual_code = hit.country_code.casefold()
        if expected_code and actual_code:
            country_score = 1.0 if expected_code == actual_code else 0.0
            country_mismatch = expected_code != actual_code
        elif candidate.country and hit.country:
            country_score = _text_similarity(
                candidate.country, hit.country
            )
            country_mismatch = country_score < 0.25
        else:
            country_score = 0.5
            country_mismatch = False
        distance = haversine_km(
            candidate.model_latitude,
            candidate.model_longitude,
            hit.latitude,
            hit.longitude,
        )
        coordinate_score = 1.0 / (1.0 + distance / 200.0)
        score = (
            0.42 * name_similarity
            + 0.18 * context_similarity
            + 0.18 * country_score
            + 0.12 * coordinate_score
            + 0.10 * clamp(hit.importance)
        )
        if country_mismatch:
            score = min(score, 0.20)
        distance_limit = max(150.0, candidate.radius_km * 4.0)
        if distance > distance_limit and name_similarity < 0.86:
            score = min(score, 0.25)
        return clamp(score)


def _text_similarity(first: str, second: str) -> float:
    normalized_first = _normalize(first)
    normalized_second = _normalize(second)
    if not normalized_first or not normalized_second:
        return 0.0
    sequence_score = difflib.SequenceMatcher(
        None, normalized_first, normalized_second
    ).ratio()
    substring_score = 0.0
    if (
        normalized_first in normalized_second
        or normalized_second in normalized_first
    ):
        substring_score = min(
            len(normalized_first), len(normalized_second)
        ) / max(len(normalized_first), len(normalized_second))
        substring_score = min(1.0, 0.65 + 0.35 * substring_score)
    first_tokens = set(
        re.findall(r"[a-z0-9]+|[\u3400-\u9fff]", first.casefold())
    )
    second_tokens = set(
        re.findall(r"[a-z0-9]+|[\u3400-\u9fff]", second.casefold())
    )
    token_score = (
        len(first_tokens & second_tokens)
        / max(1, len(first_tokens | second_tokens))
    )
    return clamp(max(sequence_score, substring_score, token_score))


def _normalize(value: str) -> str:
    return "".join(
        re.findall(r"[a-z0-9\u3400-\u9fff]+", str(value).casefold())
    )
