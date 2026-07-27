"""Best-effort local photo metadata extraction on macOS."""

from __future__ import annotations

import plistlib
import subprocess
from pathlib import Path
from typing import List

from sakugis.agent_models import Evidence


METADATA_KEYS = [
    "kMDItemLatitude",
    "kMDItemLongitude",
    "kMDItemTimestamp",
    "kMDItemPixelHeight",
    "kMDItemPixelWidth",
]


def extract_photo_metadata(path: str) -> List[Evidence]:
    source = Path(path)
    if not source.is_file():
        return []
    try:
        result = subprocess.run(
            ["/usr/bin/mdls", "-plist", "-", *sum((["-name", key] for key in METADATA_KEYS), []), str(source)],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0 or not result.stdout:
        return []
    try:
        metadata = plistlib.loads(result.stdout)
    except (plistlib.InvalidFileException, ValueError):
        return []

    evidence: List[Evidence] = []
    latitude = metadata.get("kMDItemLatitude")
    longitude = metadata.get("kMDItemLongitude")
    if isinstance(latitude, (int, float)) and isinstance(longitude, (int, float)):
        if -90 <= latitude <= 90 and -180 <= longitude <= 180:
            evidence.append(
                Evidence(
                    evidence_id="META-GPS",
                    kind="exif_gps",
                    value=f"{latitude:.7f}, {longitude:.7f}",
                    reliability=0.98,
                    source="local-metadata",
                    scale="point",
                    supports=[f"{latitude:.7f},{longitude:.7f}"],
                )
            )
    timestamp = metadata.get("kMDItemTimestamp")
    if timestamp:
        evidence.append(
            Evidence(
                evidence_id="META-TIME",
                kind="capture_time",
                value=str(timestamp),
                reliability=0.9,
                source="local-metadata",
                scale="context",
            )
        )
    return evidence
