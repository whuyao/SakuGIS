"""Create portable, human-readable Markdown reports from Agent results."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable

from sakugis.agent_models import GeoAnalysisResult
from sakugis.i18n import tr


def _cell(value: object) -> str:
    return (
        str(value or "—")
        .replace("\\", "\\\\")
        .replace("|", "\\|")
        .replace("\r", " ")
        .replace("\n", "<br>")
    )


def _text(value: object) -> str:
    return str(value or "—").replace("\r", "").strip()


def _join(values: Iterable[str]) -> str:
    cleaned = [str(value).strip() for value in values if str(value).strip()]
    return ", ".join(cleaned) if cleaned else "—"


def _check_label(check) -> str:
    translated = tr(f"gis.{check.check_id}")
    return check.label if translated.startswith("gis.") else translated


def build_markdown_report(
    result: GeoAnalysisResult, generated_at: datetime = None
) -> str:
    generated = generated_at or datetime.now().astimezone()
    image_paths = result.image_paths or (
        [result.image_path] if result.image_path else []
    )
    photo_names = [Path(path).name for path in image_paths]
    lines = [
        f"# {tr('report.title')}",
        "",
        f"> {tr('report.generated')}: {generated.isoformat(timespec='seconds')}",
        "",
        f"## {tr('report.input')}",
        "",
        f"- **{tr('report.query')}**: {_text(result.query)}",
        (
            f"- **{tr('report.photos')}**: "
            f"{_join(photo_names) if photo_names else tr('report.none')}"
        ),
        "",
        f"## {tr('report.evidence')}",
        "",
        _text(result.evidence_summary),
        "",
        (
            f"| ID | {tr('agent.evidence')} | {tr('agent.content')} | "
            f"{tr('agent.photos')} | {tr('report.reliability')} | "
            f"{tr('report.source')} |"
        ),
        "|---|---|---|---|---:|---|",
    ]
    if result.evidence:
        for evidence in result.evidence:
            lines.append(
                "| {id} | {kind} | {value} | {photos} | "
                "{reliability:.0f}% | {source} |".format(
                    id=_cell(evidence.evidence_id),
                    kind=_cell(evidence.kind),
                    value=_cell(evidence.value),
                    photos=_cell(_join(evidence.photo_ids)),
                    reliability=evidence.reliability * 100,
                    source=_cell(evidence.source),
                )
            )
    else:
        lines.append("| — | — | — | — | — | — |")

    lines.extend(
        [
            "",
            f"## {tr('report.constraints')}",
            "",
            (
                f"| {tr('report.constraint')} | {tr('agent.range')} | "
                f"{tr('report.importance')} | {tr('report.required')} | OSM tag |"
            ),
            "|---|---:|---:|---|---|",
        ]
    )
    if result.spatial_constraints:
        for constraint in result.spatial_constraints:
            tag = (
                f"{constraint.tag_key}={constraint.tag_value}"
                if constraint.tag_key
                else constraint.kind
            )
            lines.append(
                f"| {_cell(tr(f'gis.{constraint.constraint_id}'))} | "
                f"{constraint.radius_km:g} km | "
                f"{constraint.importance * 100:.0f}% | "
                f"{tr('report.yes') if constraint.required else tr('report.no')} | "
                f"{_cell(tag)} |"
            )
    else:
        lines.append("| — | — | — | — | — |")

    lines.extend(
        [
            "",
            f"## {tr('report.candidates')}",
            "",
            (
                f"| {tr('report.rank')} | ID | {tr('report.location')} | "
                f"{tr('report.coordinates')} | {tr('report.composite')} | "
                f"{tr('report.photo_consistency')} | "
                f"{tr('report.gis_score')} | {tr('report.coverage')} | "
                f"{tr('report.radius')} |"
            ),
            "|---:|---|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    if result.candidates:
        for rank, candidate in enumerate(result.candidates, 1):
            location = " · ".join(
                part
                for part in (
                    candidate.name,
                    candidate.region,
                    candidate.country,
                )
                if part
            )
            photo_match = (
                f"{candidate.photo_support_count}/{candidate.photo_total_count}"
                if candidate.photo_total_count > 1
                else "—"
            )
            lines.append(
                f"| {rank} | {_cell(candidate.candidate_id)} | {_cell(location)} | "
                f"`{candidate.latitude:.6f}, {candidate.longitude:.6f}` | "
                f"{candidate.ranking_score * 100:.1f}/100 | "
                f"{photo_match} | "
                f"{candidate.gis_score * 100:.1f}/100 | "
                f"{candidate.gis_coverage * 100:.1f}% | "
                f"{candidate.radius_km:g} km |"
            )
    else:
        lines.append("| — | — | — | — | — | — | — | — | — |")

    lines.extend(["", f"## {tr('report.details')}", ""])
    for rank, candidate in enumerate(result.candidates, 1):
        lines.extend(
            [
                f"### {rank}. {_text(candidate.name)} ({_text(candidate.candidate_id)})",
                "",
                f"- **{tr('report.reverse')}**: {_text(candidate.reverse_label)}",
                f"- **{tr('report.rationale')}**: {_text(candidate.rationale)}",
                (
                    f"- **{tr('report.support')}**: "
                    f"{_join(candidate.supporting_evidence)}"
                ),
                (
                    f"- **{tr('report.contradictions')}**: "
                    f"{_join(candidate.contradictions)}"
                ),
            ]
        )
        components = candidate.ranking_components
        if components:
            lines.append(
                f"- **{tr('report.score_breakdown')}**: "
                + tr(
                    (
                        "report.score_formula_multi"
                        if candidate.photo_total_count > 1
                        else "report.score_formula"
                    ),
                    retrieval=f"{components.get('retrieval', 0.0) * 100:.1f}",
                    model=f"{components.get('model', 0.0) * 100:.1f}",
                    effective_model=f"{components.get('effective_model', 0.0) * 100:.1f}",
                    confidence=f"{components.get('evidence_confidence', 0.0) * 100:.0f}",
                    photo=(
                        f"{components.get('effective_photo_consistency', 0.0) * 100:.0f}"
                    ),
                    gis=f"{components.get('gis', 0.0) * 100:.1f}",
                    effective_gis=f"{components.get('effective_gis', 0.0) * 100:.1f}",
                    coverage=f"{components.get('gis_coverage', 0.0) * 100:.0f}",
                    penalty=f"{components.get('contradiction_penalty', 0.0) * 100:.1f}",
                )
            )
            required_mismatches = int(
                components.get("required_mismatches", 0.0)
            )
            if required_mismatches:
                lines.append(
                    f"- {tr('report.required_mismatch', count=required_mismatches)}"
                )
            required_unknowns = int(
                components.get("required_unknowns", 0.0)
            )
            if required_unknowns:
                lines.append(
                    f"- {tr('report.required_unknown', count=required_unknowns)}"
                )
        lines.extend(
            [
                "",
                (
                    f"| {tr('report.check')} | {tr('report.result')} | "
                    f"{tr('report.nearest')} | {tr('report.source')} |"
                ),
                "|---|---|---:|---|",
            ]
        )
        if candidate.gis_checks:
            for check in candidate.gis_checks:
                if check.matched is True:
                    check_result = tr("agent.passed")
                elif check.matched is False:
                    check_result = tr("agent.failed")
                else:
                    check_result = tr("agent.unavailable")
                distance = (
                    f"{check.nearest_distance_km:g} km"
                    if check.nearest_distance_km is not None
                    else "—"
                )
                source = check.source
                if check.detail:
                    source = f"{source}; {check.detail}"
                lines.append(
                    f"| {_cell(_check_label(check))} | {_cell(check_result)} | "
                    f"{_cell(distance)} | {_cell(source)} |"
                )
        else:
            lines.append("| — | — | — | — |")
        lines.append("")

    lines.extend(
        [
            f"## {tr('report.summary')}",
            "",
            _text(result.verification_summary),
            "",
            f"- **{tr('report.backend')}**: {_text(result.gis_backend)}",
            f"- **{tr('report.model')}**: {_text(result.model)}",
            f"- {_text(result.caveat)}",
            "",
            f"> {tr('report.disclaimer')}",
            "",
            "---",
            "",
            tr("report.footer"),
            "",
        ]
    )
    return "\n".join(lines)


def write_markdown_report(path: str, result: GeoAnalysisResult) -> Path:
    destination = Path(path)
    destination.write_text(build_markdown_report(result), encoding="utf-8")
    return destination
