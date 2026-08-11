"""Portable, replayable SakuGIS project archives (``*.sgd``).

An SGD file is a versioned ZIP container.  It deliberately stores analysis
inputs and outputs, but never runtime credentials or database connection
settings.  Every payload entry is listed in the manifest with its size and
SHA-256 digest before it is accepted during loading.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import tempfile
from typing import Any, Dict, Iterable, List, Optional, Sequence
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile, ZipInfo

from sakugis.agent_models import GeoAnalysisResult
from sakugis.reporting import build_markdown_report


FORMAT_NAME = "SakuGIS Project"
FORMAT_VERSION = 1
MAX_ARCHIVE_ENTRIES = 5000
MAX_EXTRACTED_BYTES = 8 * 1024 * 1024 * 1024


class SgdError(Exception):
    """Base error for invalid or unreadable SGD projects."""


class SgdFormatError(SgdError):
    """The archive structure or format version is invalid."""


class SgdIntegrityError(SgdError):
    """A packaged file failed size or checksum validation."""


@dataclass(frozen=True)
class ArchiveAsset:
    """A local file copied into a stable location inside the SGD archive."""

    source_path: str
    archive_path: str


@dataclass
class LoadedSgdProject:
    query: str
    image_paths: List[str]
    result: Optional[GeoAnalysisResult]
    process: Dict[str, Any]
    map_state: Dict[str, Any]
    place_details: Dict[str, Any]
    manifest: Dict[str, Any]
    extraction_root: Path
    warnings: List[str] = field(default_factory=list)


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _safe_archive_path(value: str) -> str:
    if not value or "\\" in value or value.startswith("/"):
        raise SgdFormatError(f"Unsafe archive path: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise SgdFormatError(f"Unsafe archive path: {value!r}")
    return str(path)


def _is_zip_symlink(info: ZipInfo) -> bool:
    mode = (info.external_attr >> 16) & 0xFFFF
    return stat.S_ISLNK(mode)


def _digest_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _process_snapshot(result: Optional[GeoAnalysisResult]) -> Dict[str, Any]:
    if result is None:
        return {"completed": False, "stages": []}
    return {
        "completed": True,
        "case_mode": result.case_mode,
        "model": result.model,
        "retrieval_backend": result.retrieval_backend,
        "gis_backend": result.gis_backend,
        "confidence_status": result.confidence_status,
        "stages": [
            {
                "agent": 1,
                "name": "multimodal_evidence",
                "evidence_count": len(result.evidence),
            },
            {
                "agent": 2,
                "name": "place_retrieval",
                "candidate_count": len(result.candidates),
                "resolved_count": result.retrieval_resolved_count,
            },
            {
                "agent": 3,
                "name": "gis_verification",
                "check_count": sum(
                    len(candidate.gis_checks) for candidate in result.candidates
                ),
            },
        ],
    }


def _photo_archive_path(index: int, source: Path) -> str:
    suffix = source.suffix.lower()
    if not suffix or len(suffix) > 12 or not suffix[1:].isalnum():
        suffix = ".bin"
    return f"photos/P{index + 1}{suffix}"


def save_sgd(
    destination: str,
    *,
    query: str,
    image_paths: Sequence[str],
    result: Optional[GeoAnalysisResult],
    map_state: Optional[Dict[str, Any]] = None,
    place_details: Optional[Dict[str, Any]] = None,
    assets: Iterable[ArchiveAsset] = (),
    application_version: str = "",
) -> Path:
    """Atomically write a complete SGD project and return its final path."""

    final_path = Path(destination).expanduser()
    if final_path.suffix.lower() != ".sgd":
        final_path = final_path.with_suffix(".sgd")
    final_path.parent.mkdir(parents=True, exist_ok=True)

    payloads: Dict[str, bytes] = {}
    file_assets: Dict[str, Path] = {}
    photo_records: List[Dict[str, str]] = []
    for index, raw_path in enumerate(image_paths):
        source = Path(raw_path).expanduser().resolve()
        if not source.is_file():
            raise SgdError(f"Input photo no longer exists: {source}")
        archive_path = _photo_archive_path(index, source)
        file_assets[archive_path] = source
        photo_records.append(
            {
                "id": f"P{index + 1}",
                "archive_path": archive_path,
                "original_name": source.name,
            }
        )

    for asset in assets:
        archive_path = _safe_archive_path(asset.archive_path)
        source = Path(asset.source_path).expanduser().resolve()
        if not source.is_file():
            raise SgdError(f"Project asset no longer exists: {source}")
        if archive_path in file_assets or archive_path in payloads:
            raise SgdFormatError(f"Duplicate archive path: {archive_path}")
        file_assets[archive_path] = source

    case_data = {
        "query_path": "case/query.txt",
        "photos": photo_records,
        "has_analysis_result": result is not None,
        "case_mode": result.case_mode if result else "same_location",
    }
    payloads["case/query.txt"] = query.encode("utf-8")
    payloads["case/case.json"] = _json_bytes(case_data)
    payloads["map/state.json"] = _json_bytes(map_state or {})
    payloads["places/details.json"] = _json_bytes(place_details or {})
    process = _process_snapshot(result)
    process["saved_at"] = datetime.now(timezone.utc).isoformat()
    payloads["analysis/process.json"] = _json_bytes(process)

    if result is not None:
        serialized_result = result.to_dict()
        archived_photos = [item["archive_path"] for item in photo_records]
        serialized_result["query"] = query
        serialized_result["image_paths"] = archived_photos
        serialized_result["image_path"] = archived_photos[0] if archived_photos else ""
        payloads["analysis/result.json"] = _json_bytes(serialized_result)
        payloads["report/report.md"] = build_markdown_report(result).encode("utf-8")

    reserved = {"manifest.json", *payloads.keys()}
    collision = reserved.intersection(file_assets)
    if collision:
        raise SgdFormatError(
            f"Asset path collides with a project record: {sorted(collision)[0]}"
        )

    files: Dict[str, Dict[str, Any]] = {}
    for archive_path, content in payloads.items():
        safe_path = _safe_archive_path(archive_path)
        files[safe_path] = {
            "size": len(content),
            "sha256": _digest_bytes(content),
        }
    for archive_path, source in file_assets.items():
        safe_path = _safe_archive_path(archive_path)
        files[safe_path] = {
            "size": source.stat().st_size,
            "sha256": _digest_file(source),
        }
    if len(files) + 1 > MAX_ARCHIVE_ENTRIES:
        raise SgdFormatError("The project contains too many files.")
    if sum(int(record["size"]) for record in files.values()) > MAX_EXTRACTED_BYTES:
        raise SgdFormatError("The project payload is too large.")

    manifest = {
        "format": FORMAT_NAME,
        "format_version": FORMAT_VERSION,
        "application": "SakuGIS",
        "application_version": application_version,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "entry_points": {
            "case": "case/case.json",
            "map": "map/state.json",
            "places": "places/details.json",
            "process": "analysis/process.json",
            "result": "analysis/result.json" if result else "",
            "report": "report/report.md" if result else "",
        },
        "files": files,
        "privacy": {
            "credentials_included": False,
            "database_connections_included": False,
        },
    }

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{final_path.name}.", suffix=".tmp", dir=str(final_path.parent)
    )
    os.close(descriptor)
    temporary_path = Path(temporary_name)
    try:
        with ZipFile(temporary_path, "w", compression=ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", _json_bytes(manifest))
            for archive_path, content in payloads.items():
                archive.writestr(archive_path, content)
            for archive_path, source in file_assets.items():
                archive.write(source, archive_path)
        os.replace(temporary_path, final_path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
    return final_path


def _read_json(root: Path, archive_path: str) -> Dict[str, Any]:
    if not archive_path:
        return {}
    path = root.joinpath(*PurePosixPath(_safe_archive_path(archive_path)).parts)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SgdFormatError(f"Invalid JSON project record: {archive_path}") from exc
    if not isinstance(value, dict):
        raise SgdFormatError(f"Project record is not an object: {archive_path}")
    return value


def load_sgd(source: str, extraction_root: str) -> LoadedSgdProject:
    """Validate and extract an SGD project into a caller-owned directory."""

    archive_path = Path(source).expanduser()
    root = Path(extraction_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    try:
        with ZipFile(archive_path, "r") as archive:
            infos = archive.infolist()
            if len(infos) > MAX_ARCHIVE_ENTRIES:
                raise SgdFormatError("The project contains too many files.")
            names = set()
            total_size = 0
            for info in infos:
                name = _safe_archive_path(info.filename.rstrip("/"))
                if name in names:
                    raise SgdFormatError(f"Duplicate archive entry: {name}")
                names.add(name)
                if _is_zip_symlink(info):
                    raise SgdFormatError(f"Symbolic links are not allowed: {name}")
                total_size += info.file_size
            if total_size > MAX_EXTRACTED_BYTES:
                raise SgdFormatError("The extracted project is too large.")
            if "manifest.json" not in names:
                raise SgdFormatError("The project manifest is missing.")
            try:
                manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
            except (UnicodeError, json.JSONDecodeError) as exc:
                raise SgdFormatError("The project manifest is invalid.") from exc
            if not isinstance(manifest, dict) or manifest.get("format") != FORMAT_NAME:
                raise SgdFormatError("This is not a SakuGIS project.")
            if manifest.get("format_version") != FORMAT_VERSION:
                raise SgdFormatError(
                    f"Unsupported SGD format version: {manifest.get('format_version')}"
                )
            manifest_files = manifest.get("files")
            if not isinstance(manifest_files, dict):
                raise SgdFormatError("The project file index is invalid.")
            expected_names = {"manifest.json", *manifest_files.keys()}
            if names != expected_names:
                raise SgdFormatError("The archive does not match its file index.")

            for name, record in manifest_files.items():
                safe_name = _safe_archive_path(name)
                if not isinstance(record, dict):
                    raise SgdFormatError(f"Invalid file record: {safe_name}")
                info = archive.getinfo(safe_name)
                expected_size = int(record.get("size", -1))
                if expected_size != info.file_size:
                    raise SgdIntegrityError(f"Size check failed: {safe_name}")
                destination = root.joinpath(*PurePosixPath(safe_name).parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                digest = hashlib.sha256()
                written = 0
                with archive.open(info, "r") as source_handle, destination.open("wb") as output:
                    while True:
                        chunk = source_handle.read(1024 * 1024)
                        if not chunk:
                            break
                        written += len(chunk)
                        if written > expected_size:
                            raise SgdIntegrityError(f"Size check failed: {safe_name}")
                        digest.update(chunk)
                        output.write(chunk)
                if written != expected_size or digest.hexdigest() != record.get("sha256"):
                    raise SgdIntegrityError(f"Checksum failed: {safe_name}")
    except (BadZipFile, OSError, RuntimeError) as exc:
        raise SgdFormatError(f"Cannot read SGD project: {archive_path}") from exc

    entry_points = manifest.get("entry_points") or {}
    case = _read_json(root, str(entry_points.get("case") or "case/case.json"))
    map_state = _read_json(root, str(entry_points.get("map") or "map/state.json"))
    place_details = _read_json(
        root, str(entry_points.get("places") or "places/details.json")
    )
    process = _read_json(
        root, str(entry_points.get("process") or "analysis/process.json")
    )
    query_path = str(case.get("query_path") or "case/query.txt")
    query_file = root.joinpath(*PurePosixPath(_safe_archive_path(query_path)).parts)
    try:
        query = query_file.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise SgdFormatError("The saved query cannot be read.") from exc

    image_paths: List[str] = []
    for photo in case.get("photos") or []:
        if not isinstance(photo, dict):
            continue
        saved_path = str(photo.get("archive_path") or "")
        if saved_path:
            image_paths.append(
                str(root.joinpath(*PurePosixPath(_safe_archive_path(saved_path)).parts))
            )

    result = None
    result_entry = str(entry_points.get("result") or "")
    if result_entry:
        result = GeoAnalysisResult.from_dict(_read_json(root, result_entry))
        result.query = query
        result.image_paths = list(image_paths)
        result.image_path = image_paths[0] if image_paths else ""

    warnings = [
        str(item)
        for item in map_state.get("warnings", [])
        if str(item).strip()
    ]
    return LoadedSgdProject(
        query=query,
        image_paths=image_paths,
        result=result,
        process=process,
        map_state=map_state,
        place_details=place_details,
        manifest=manifest,
        extraction_root=root,
        warnings=warnings,
    )
