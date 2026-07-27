#!/usr/bin/env python3
"""Run one end-to-end text query without opening the desktop interface."""

from __future__ import annotations

import argparse

from sakugis.geo_agents import GeoAgentPipeline
from sakugis.i18n import set_language
from sakugis.reporting import write_markdown_report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("query")
    parser.add_argument("--language", choices=("zh_CN", "en"), default="zh_CN")
    parser.add_argument("--report")
    arguments = parser.parse_args()
    set_language(arguments.language)

    result = GeoAgentPipeline().run(
        query=arguments.query,
        progress=lambda percent, message: print(f"[{percent:3d}%] {message}"),
    )
    print(f"backend={result.gis_backend}")
    for rank, candidate in enumerate(result.candidates, 1):
        print(
            "{rank}. {name} ({lat:.5f}, {lon:.5f}) "
            "score={score:.1f} gis={gis:.1f} coverage={coverage:.0f}%".format(
                rank=rank,
                name=candidate.name,
                lat=candidate.latitude,
                lon=candidate.longitude,
                score=candidate.ranking_score * 100.0,
                gis=candidate.gis_score * 100.0,
                coverage=candidate.gis_coverage * 100.0,
            )
        )
    if arguments.report:
        write_markdown_report(arguments.report, result)
        print(f"report={arguments.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
