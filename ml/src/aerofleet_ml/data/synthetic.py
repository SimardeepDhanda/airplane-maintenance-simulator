"""Small, explicitly SYNTHETIC dataset in C-MAPSS file format, for tests and CI only.

It imitates the shape of the data (26 columns, run-to-failure train units, truncated test units
with a RUL file) with a simple exponential degradation signal. It is not NASA data and any metrics
computed on it are meaningless as model performance claims. SOURCE.json marks it `synthetic: true`,
and the pipeline labels resulting artifacts `data_kind: synthetic_fixture`.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from aerofleet_ml.data.cmapss import COLUMNS

_INFORMATIVE = {
    "sensor_2": 0.5,
    "sensor_4": 9.0,
    "sensor_7": -0.9,
    "sensor_11": 0.27,
    "sensor_12": -0.7,
}


def _trajectory(rng: np.random.Generator, unit: int, life: int, stop: int) -> list[str]:
    rows = []
    onset = rng.uniform(0.3, 0.6) * life
    for cycle in range(1, stop + 1):
        wear = np.exp(max(0.0, cycle - onset) / (life - onset) * 2.0) - 1.0
        values = [float(unit), float(cycle), rng.normal(0, 0.002), rng.normal(0, 0.0003), 100.0]
        for column in COLUMNS[5:]:
            base = 100.0 + 10 * int(column.split("_")[1])
            drift = _INFORMATIVE.get(column, 0.0) * wear
            noise = rng.normal(0, 0.2) if column in _INFORMATIVE else 0.0
            values.append(base + drift + noise)
        rows.append(" ".join(f"{v:.4f}" for v in values))
    return rows


def write_synthetic_dataset(
    directory: Path, subset: str = "FD001", n_train: int = 30, n_test: int = 12, seed: int = 0
) -> Path:
    rng = np.random.default_rng(seed)
    directory.mkdir(parents=True, exist_ok=True)
    train_rows: list[str] = []
    for unit in range(1, n_train + 1):
        life = int(rng.integers(120, 220))
        train_rows += _trajectory(rng, unit, life, life)
    test_rows: list[str] = []
    final_rul: list[int] = []
    for unit in range(1, n_test + 1):
        life = int(rng.integers(120, 220))
        stop = int(rng.integers(30, life - 5))
        test_rows += _trajectory(rng, unit, life, stop)
        final_rul.append(life - stop)
    (directory / f"train_{subset}.txt").write_text("\n".join(train_rows) + "\n")
    (directory / f"test_{subset}.txt").write_text("\n".join(test_rows) + "\n")
    (directory / f"RUL_{subset}.txt").write_text("\n".join(map(str, final_rul)) + "\n")
    (directory / "SOURCE.json").write_text(
        json.dumps(
            {"synthetic": True, "archive_sha256": None, "files": {}, "source": "synthetic fixture"},
            indent=2,
        )
    )
    return directory
