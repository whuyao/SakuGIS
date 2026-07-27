"""Optional PostGIS-backed verification for a normalized OSM feature table."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Sequence, Tuple

from sakugis.agent_models import Candidate
from sakugis.credentials import get_postgis_dsn
from sakugis.gis_models import GISCheck, ReversePlace, SpatialConstraint


_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class PostGISError(RuntimeError):
    pass


@dataclass(frozen=True)
class PostGISConfig:
    dsn: str = ""
    table: str = "public.sakugis_osm_features"

    @classmethod
    def from_environment(cls) -> "PostGISConfig":
        return cls(
            dsn=get_postgis_dsn(),
            table=os.environ.get(
                "SAKUGIS_POSTGIS_TABLE", "public.sakugis_osm_features"
            ).strip(),
        )

    @property
    def enabled(self) -> bool:
        return bool(self.dsn)

    @property
    def quoted_table(self) -> str:
        parts = self.table.split(".")
        if not 1 <= len(parts) <= 2 or not all(_IDENTIFIER.match(part) for part in parts):
            raise PostGISError("Invalid PostGIS table name")
        return ".".join(f'"{part}"' for part in parts)


class PostGISProvider:
    def __init__(self, config: PostGISConfig = None):
        self.config = config or PostGISConfig.from_environment()

    @property
    def enabled(self) -> bool:
        return self.config.enabled

    def verify(
        self,
        candidates: Sequence[Candidate],
        constraints: Sequence[SpatialConstraint],
    ) -> Tuple[Dict[str, ReversePlace], Dict[str, List[GISCheck]]]:
        if not self.enabled:
            raise PostGISError("PostGIS is not configured")
        try:
            import psycopg
        except ImportError as exc:
            raise PostGISError("psycopg is not available") from exc

        table = self.config.quoted_table
        reverse: Dict[str, ReversePlace] = {}
        checks: Dict[str, List[GISCheck]] = {
            candidate.candidate_id: [] for candidate in candidates
        }
        try:
            with psycopg.connect(self.config.dsn, connect_timeout=5) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT PostGIS_Version()")
                    cursor.fetchone()
                    for candidate in candidates:
                        reverse[candidate.candidate_id] = self._reverse(
                            cursor, table, candidate
                        )
                        checks[candidate.candidate_id] = self._checks(
                            cursor, table, candidate, constraints
                        )
        except Exception as exc:
            raise PostGISError("PostGIS verification failed") from exc
        return reverse, checks

    @staticmethod
    def _reverse(cursor: Any, table: str, candidate: Candidate) -> ReversePlace:
        query = f"""
            SELECT
                COALESCE(name, tags->>'name:en', tags->>'name:zh', ''),
                tags,
                CASE
                  WHEN COALESCE(tags->>'admin_level', '') ~ '^[0-9]+$'
                  THEN (tags->>'admin_level')::integer
                  ELSE 99
                END AS admin_level
            FROM {table}
            WHERE tags->>'boundary' = 'administrative'
              AND ST_Covers(
                    geom,
                    ST_SetSRID(ST_MakePoint(%s, %s), 4326)
                  )
            ORDER BY admin_level DESC
            LIMIT 20
        """
        cursor.execute(query, (candidate.longitude, candidate.latitude))
        rows = cursor.fetchall()
        country = ""
        country_code = ""
        region = ""
        locality = ""
        labels = []
        aliases = []
        for name, tags, admin_level in rows:
            tags = tags if isinstance(tags, dict) else {}
            label = str(name or "")
            if label:
                labels.append(label)
            aliases.extend(
                str(tags.get(key))
                for key in ("name", "name:en", "name:zh")
                if tags.get(key)
            )
            if admin_level == 2:
                country = label
                country_code = str(
                    tags.get("ISO3166-1:alpha2")
                    or tags.get("ISO3166-1")
                    or ""
                ).upper()
            elif admin_level in {3, 4, 5, 6} and not region:
                region = label
            elif admin_level >= 7 and not locality:
                locality = label
        return ReversePlace(
            display_name=", ".join(labels),
            country=country,
            country_code=country_code,
            region=region,
            locality=locality,
            source="PostGIS",
            aliases=list(dict.fromkeys(aliases)),
        )

    @staticmethod
    def _checks(
        cursor: Any,
        table: str,
        candidate: Candidate,
        constraints: Sequence[SpatialConstraint],
    ) -> List[GISCheck]:
        checks = []
        query = f"""
            SELECT
                COALESCE(name, tags->>'name:en', tags->>'name:zh', ''),
                ST_Distance(
                    geom::geography,
                    ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography
                ) / 1000.0 AS distance_km
            FROM {table}
            WHERE ST_DWithin(
                    geom::geography,
                    ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
                    %s
                  )
              AND tags->>%s = %s
            ORDER BY distance_km
            LIMIT 200
        """
        for constraint in constraints:
            if constraint.kind != "osm_tag":
                continue
            cursor.execute(
                query,
                (
                    candidate.longitude,
                    candidate.latitude,
                    candidate.longitude,
                    candidate.latitude,
                    constraint.radius_km * 1000.0,
                    constraint.tag_key,
                    constraint.tag_value,
                ),
            )
            rows = cursor.fetchall()
            names = [str(row[0]) for row in rows[:3] if row[0]]
            checks.append(
                GISCheck(
                    check_id=constraint.constraint_id,
                    kind="spatial_constraint",
                    label=constraint.label,
                    matched=bool(rows),
                    source="PostGIS",
                    count=len(rows),
                    nearest_distance_km=(
                        round(float(rows[0][1]), 2) if rows else None
                    ),
                    detail=", ".join(names),
                    strength=(
                        max(
                            0.60,
                            1.0
                            - 0.40
                            * float(rows[0][1])
                            / max(0.1, constraint.radius_km),
                        )
                        if rows
                        else 0.15
                    ),
                    weight=constraint.importance,
                    required=constraint.required,
                )
            )
        return checks
