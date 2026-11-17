"""Acquisition and validation tests. Fixtures here are tiny synthetic files, not NASA data."""

import hashlib
import io
import json
import zipfile
from pathlib import Path

import pytest

from aerofleet_ml.data.cmapss import (
    COLUMNS,
    EXPECTED_FILES,
    SOURCE_URL,
    DatasetError,
    acquire,
    validate_subset,
)


def _row(unit: int, cycle: int) -> str:
    values = [str(unit), str(cycle)] + ["0.5"] * (len(COLUMNS) - 2)
    return " ".join(values) + "  \n"  # trailing spaces, as in the real files


def _synthetic_files(units: int = 2) -> dict[str, bytes]:
    files: dict[str, bytes] = {"readme.txt": b"synthetic fixture\n"}
    for name in EXPECTED_FILES:
        if name.startswith(("train_", "test_")):
            lines = [_row(u, c) for u in range(1, units + 1) for c in range(1, 4)]
            files[name] = "".join(lines).encode()
        elif name.startswith("RUL_"):
            files[name] = "".join(f"{10 * u}\n" for u in range(1, units + 1)).encode()
    return files


def _zip(members: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    return buffer.getvalue()


def _write_archive(tmp_path: Path, data: bytes) -> tuple[str, dict[str, str]]:
    path = tmp_path / "archive.zip"
    path.write_bytes(data)
    return str(path), {hashlib.sha256(data).hexdigest(): "test fixture"}


def test_extracts_nested_archive_and_records_provenance(tmp_path: Path) -> None:
    inner = _zip(_synthetic_files())
    source, checksums = _write_archive(tmp_path, _zip({"Outer Folder/CMAPSSData.zip": inner}))

    record = acquire(source, tmp_path / "raw", known_checksums=checksums)

    out = tmp_path / "raw" / "cmapss"
    assert sorted(p.name for p in out.iterdir()) == sorted([*EXPECTED_FILES, "SOURCE.json"])
    manifest = json.loads((out / "SOURCE.json").read_text())
    assert manifest["archive_sha256"] == record.archive_sha256
    assert (
        manifest["files"]["train_FD001.txt"]
        == hashlib.sha256((out / "train_FD001.txt").read_bytes()).hexdigest()
    )


def test_rejects_unknown_checksum(tmp_path: Path) -> None:
    source, _ = _write_archive(tmp_path, _zip(_synthetic_files()))
    with pytest.raises(DatasetError, match="Unrecognised archive checksum"):
        acquire(source, tmp_path / "raw", known_checksums={"0" * 64: "other"})
    assert not (tmp_path / "raw" / "cmapss").exists()


def test_reports_missing_files(tmp_path: Path) -> None:
    files = _synthetic_files()
    del files["RUL_FD003.txt"]
    source, checksums = _write_archive(tmp_path, _zip(files))
    with pytest.raises(DatasetError, match=r"RUL_FD003\.txt"):
        acquire(source, tmp_path / "raw", known_checksums=checksums)


def test_ignores_archive_paths_outside_destination(tmp_path: Path) -> None:
    files = {f"../../{name}": data for name, data in _synthetic_files().items()}
    source, checksums = _write_archive(tmp_path, _zip(files))
    acquire(source, tmp_path / "raw", known_checksums=checksums)
    assert (tmp_path / "raw" / "cmapss" / "train_FD001.txt").is_file()
    assert not (tmp_path / "train_FD001.txt").exists()


def test_failed_rerun_keeps_previous_dataset(tmp_path: Path) -> None:
    good, checksums = _write_archive(tmp_path, _zip(_synthetic_files()))
    acquire(good, tmp_path / "raw", known_checksums=checksums)
    bad = tmp_path / "bad.zip"
    bad.write_bytes(b"not a zip")
    with pytest.raises(DatasetError):
        acquire(
            str(bad),
            tmp_path / "raw",
            known_checksums={hashlib.sha256(b"not a zip").hexdigest(): "x"},
        )
    assert (tmp_path / "raw" / "cmapss" / "train_FD001.txt").is_file()


def test_rejects_non_https_url(tmp_path: Path) -> None:
    with pytest.raises(DatasetError, match="neither an existing file nor an https URL"):
        acquire("http://example.invalid/data.zip", tmp_path)


def test_validate_subset_counts(tmp_path: Path) -> None:
    for name, data in _synthetic_files(units=3).items():
        (tmp_path / name).write_bytes(data)
    stats = validate_subset(tmp_path, "FD001")
    assert (stats.train_rows, stats.train_units, stats.test_units, stats.rul_rows) == (9, 3, 3, 3)


def test_validate_subset_rejects_wrong_column_count(tmp_path: Path) -> None:
    for name, data in _synthetic_files().items():
        (tmp_path / name).write_bytes(data)
    (tmp_path / "train_FD001.txt").write_text("1 1 0.1\n")
    with pytest.raises(DatasetError, match=r"train_FD001.txt:1: expected 26 columns, got 3"):
        validate_subset(tmp_path, "FD001")


def test_validate_subset_rejects_rul_unit_mismatch(tmp_path: Path) -> None:
    for name, data in _synthetic_files(units=2).items():
        (tmp_path / name).write_bytes(data)
    (tmp_path / "RUL_FD001.txt").write_text("10\n")
    with pytest.raises(DatasetError, match=r"1 rows but test_FD001\.txt has 2 units"):
        validate_subset(tmp_path, "FD001")


@pytest.mark.network
def test_real_nasa_archive_matches_published_counts(tmp_path: Path) -> None:
    """Downloads the real archive (~12 MB). Counts for FD001 come from the dataset readme
    (100 train / 100 test trajectories); row counts were measured from the files."""
    acquire(SOURCE_URL, tmp_path)
    stats = validate_subset(tmp_path / "cmapss", "FD001")
    assert (stats.train_units, stats.test_units, stats.rul_rows) == (100, 100, 100)
    assert (stats.train_rows, stats.test_rows) == (20631, 13096)
