"""Acquire and structurally validate the NASA C-MAPSS turbofan dataset.

Source: NASA PCoE Data Set Repository, entry 6 "Turbofan Engine Degradation Simulation".
The distributed archive is a ZIP containing a second ZIP (CMAPSSData.zip) with the text files.
Both archives are accepted as input and verified against known SHA-256 checksums.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import shutil
import urllib.request
import zipfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

SOURCE_URL = "https://phm-datasets.s3.amazonaws.com/NASA/6.+Turbofan+Engine+Degradation+Simulation+Data+Set.zip"
# Measured on 2026-11-17 from SOURCE_URL (outer) and the CMAPSSData.zip it contains (inner).
KNOWN_ARCHIVE_SHA256 = {
    "c9c5dec12a945a82e8bb4446589d7fb3cc057b5e5d81fa1a12e25ee9912ad3b2": "outer distribution zip",
    "74bef434a34db25c7bf72e668ea4cd52afe5f2cf8e44367c55a82bfd91a5a34f": "inner CMAPSSData.zip",
}

SUBSETS = ("FD001", "FD002", "FD003", "FD004")
EXPECTED_FILES = (
    *(f"{kind}_{subset}.txt" for subset in SUBSETS for kind in ("train", "test", "RUL")),
    "readme.txt",
)

# The readme lists "sensor measurement 1 ... 26", but rows have 26 columns in total:
# unit, cycle, 3 operational settings, and 21 sensors. Verified against the files.
COLUMNS = (
    "unit_id",
    "cycle",
    "setting_1",
    "setting_2",
    "setting_3",
    *(f"sensor_{i}" for i in range(1, 22)),
)

_MEMBER_PATTERN = re.compile(r"^((train|test|RUL)_FD00[1-4]\.txt|readme\.txt)$")
_DOWNLOAD_TIMEOUT_S = 60


class DatasetError(RuntimeError):
    """Raised with an actionable message when acquisition or validation fails."""


@dataclass(frozen=True)
class AcquisitionRecord:
    source: str
    archive_sha256: str
    archive_kind: str
    retrieved_at: str
    files: dict[str, str]  # file name -> sha256


@dataclass(frozen=True)
class SubsetStats:
    subset: str
    train_rows: int
    train_units: int
    test_rows: int
    test_units: int
    rul_rows: int


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_source(source: str) -> bytes:
    path = Path(source).expanduser()
    if path.is_file():
        return path.read_bytes()
    if not source.startswith("https://"):
        raise DatasetError(f"Source is neither an existing file nor an https URL: {source}")
    try:
        with urllib.request.urlopen(source, timeout=_DOWNLOAD_TIMEOUT_S) as response:
            data: bytes = response.read()
    except OSError as exc:
        raise DatasetError(
            f"Download failed ({exc}). Download the archive manually from the NASA PCoE "
            "repository and rerun with --source /path/to/archive.zip"
        ) from exc
    return data


def _collect_members(archive: zipfile.ZipFile, found: dict[str, bytes], depth: int = 0) -> None:
    for info in archive.infolist():
        if info.is_dir():
            continue
        name = Path(info.filename).name  # basename only: never trust archive paths
        if name.lower().endswith(".zip") and depth == 0:
            with zipfile.ZipFile(io.BytesIO(archive.read(info))) as inner:
                _collect_members(inner, found, depth + 1)
        elif _MEMBER_PATTERN.match(name):
            found[name] = archive.read(info)


def acquire(
    source: str,
    destination: Path,
    known_checksums: dict[str, str] | None = None,
) -> AcquisitionRecord:
    """Fetch the archive, verify its checksum, and extract the dataset files into destination."""
    checksums = KNOWN_ARCHIVE_SHA256 if known_checksums is None else known_checksums
    data = _read_source(source)
    digest = _sha256(data)
    if digest not in checksums:
        raise DatasetError(
            f"Unrecognised archive checksum {digest}. Expected one of: "
            f"{', '.join(checksums)}. The file may be corrupt, truncated, or a different release."
        )
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            found: dict[str, bytes] = {}
            _collect_members(archive, found)
    except zipfile.BadZipFile as exc:
        raise DatasetError(f"Source is not a valid ZIP archive: {exc}") from exc

    missing = sorted(set(EXPECTED_FILES) - set(found))
    if missing:
        raise DatasetError(f"Archive is missing expected files: {', '.join(missing)}")

    target = destination / "cmapss"
    staging = destination / ".cmapss.partial"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    for name in EXPECTED_FILES:
        (staging / name).write_bytes(found[name])

    record = AcquisitionRecord(
        source=source,
        archive_sha256=digest,
        archive_kind=checksums[digest],
        retrieved_at=datetime.now(UTC).isoformat(timespec="seconds"),
        files={name: _sha256(found[name]) for name in EXPECTED_FILES},
    )
    (staging / "SOURCE.json").write_text(json.dumps(asdict(record), indent=2) + "\n")
    shutil.rmtree(target, ignore_errors=True)
    staging.rename(target)  # replace atomically so a failed run never leaves a half dataset
    return record


def _parse_rows(path: Path, expected_columns: int) -> list[list[float]]:
    rows: list[list[float]] = []
    for line_number, line in enumerate(path.read_text().splitlines(), start=1):
        fields = line.split()
        if not fields:
            continue
        if len(fields) != expected_columns:
            raise DatasetError(
                f"{path.name}:{line_number}: expected {expected_columns} columns, got {len(fields)}"
            )
        try:
            rows.append([float(value) for value in fields])
        except ValueError as exc:
            raise DatasetError(f"{path.name}:{line_number}: non-numeric value ({exc})") from exc
    if not rows:
        raise DatasetError(f"{path.name} contains no rows")
    return rows


def validate_subset(dataset_dir: Path, subset: str) -> SubsetStats:
    """Check column counts, numeric content, and that RUL rows match test units."""
    if subset not in SUBSETS:
        raise DatasetError(f"Unknown subset {subset!r}; expected one of {SUBSETS}")
    train = _parse_rows(dataset_dir / f"train_{subset}.txt", len(COLUMNS))
    test = _parse_rows(dataset_dir / f"test_{subset}.txt", len(COLUMNS))
    rul = _parse_rows(dataset_dir / f"RUL_{subset}.txt", 1)
    test_units = len({row[0] for row in test})
    if len(rul) != test_units:
        raise DatasetError(
            f"RUL_{subset}.txt has {len(rul)} rows but test_{subset}.txt has {test_units} units"
        )
    return SubsetStats(
        subset=subset,
        train_rows=len(train),
        train_units=len({row[0] for row in train}),
        test_rows=len(test),
        test_units=test_units,
        rul_rows=len(rul),
    )
