"""Re-runs the real FD001 pipeline and checks it reproduces the committed artifact metadata.

Requires the NASA data in data/raw/cmapss (`make data`). Run with `pytest -m dataset`.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from aerofleet_ml.pipeline import run_pipeline

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data" / "raw" / "cmapss"
ARTIFACTS = REPO_ROOT / "ml" / "artifacts"


def _numbers(obj: Any, prefix: str = "") -> dict[str, float]:
    out: dict[str, float] = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            out |= _numbers(v, f"{prefix}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out |= _numbers(v, f"{prefix}[{i}]")
    elif isinstance(obj, int | float) and not isinstance(obj, bool):
        out[prefix] = float(obj)
    return out


@pytest.mark.dataset
def test_committed_metrics_are_reproducible(tmp_path: Path) -> None:
    if not (DATA_DIR / "SOURCE.json").is_file():
        pytest.fail("NASA data missing: run `make data` before `pytest -m dataset`")
    committed_version = (ARTIFACTS / "LATEST").read_text().strip()
    committed = json.loads((ARTIFACTS / committed_version / "metrics.json").read_text())

    result = run_pipeline(DATA_DIR, tmp_path)
    fresh = json.loads((result.artifact_dir / "metrics.json").read_text())

    assert result.model_version == committed_version
    assert fresh["data_kind"] == "nasa_cmapss"
    expected, actual = _numbers(committed["test"]), _numbers(fresh["test"])
    assert expected.keys() == actual.keys()
    for key, value in expected.items():
        assert actual[key] == pytest.approx(value, rel=1e-4, abs=1e-6), key
