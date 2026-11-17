"""Load C-MAPSS text files into DataFrames and derive RUL targets.

Targets are measured in engine cycles. They are a modelling target ("cycles to simulated failure"),
not a certified maintenance limit.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from aerofleet_ml.data.cmapss import COLUMNS, SUBSETS, DatasetError

UNIT = "unit_id"
CYCLE = "cycle"
TARGET = "rul"


def _read_table(path: Path) -> pd.DataFrame:
    if not path.is_file():
        raise DatasetError(f"{path} not found. Run `make data` first.")
    frame = pd.read_csv(path, sep=r"\s+", header=None, names=list(COLUMNS), engine="python")
    if frame.isna().any().any():
        raise DatasetError(f"{path.name} has missing values or ragged rows")
    frame[UNIT] = frame[UNIT].astype("int64")
    frame[CYCLE] = frame[CYCLE].astype("int64")
    return frame.sort_values([UNIT, CYCLE], kind="stable").reset_index(drop=True)


def add_train_targets(frame: pd.DataFrame) -> pd.DataFrame:
    """Run-to-failure trajectories: RUL(i, t) = max_cycle(i) - t."""
    out = frame.copy()
    out[TARGET] = out.groupby(UNIT)[CYCLE].transform("max") - out[CYCLE]
    return out


def add_test_targets(frame: pd.DataFrame, final_rul: pd.Series) -> pd.DataFrame:
    """Truncated trajectories: RUL(i, t) = RUL_final(i) + (last_cycle(i) - t).

    `final_rul` is indexed by unit id and gives the true RUL at each unit's last observed cycle.
    """
    units = frame[UNIT].unique()
    missing = sorted(set(units) - set(final_rul.index))
    if missing:
        raise DatasetError(f"No final RUL for test units {missing[:5]}")
    out = frame.copy()
    last_cycle = out.groupby(UNIT)[CYCLE].transform("max")
    out[TARGET] = out[UNIT].map(final_rul).astype("int64") + (last_cycle - out[CYCLE])
    return out


def load_subset(dataset_dir: Path, subset: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (train, test) frames, both with a `rul` column."""
    if subset not in SUBSETS:
        raise DatasetError(f"Unknown subset {subset!r}")
    train = add_train_targets(_read_table(dataset_dir / f"train_{subset}.txt"))
    test = _read_table(dataset_dir / f"test_{subset}.txt")
    rul_values = (dataset_dir / f"RUL_{subset}.txt").read_text().split()
    test_units = sorted(test[UNIT].unique())
    if len(rul_values) != len(test_units):
        raise DatasetError(
            f"RUL_{subset}.txt has {len(rul_values)} values for {len(test_units)} test units"
        )
    # Line i of RUL_FDxxx.txt corresponds to test unit i (units are numbered 1..N).
    final_rul = pd.Series([int(float(v)) for v in rul_values], index=test_units)
    return train, add_test_targets(test, final_rul)


def last_cycle_rows(frame: pd.DataFrame) -> pd.DataFrame:
    """One row per unit: its final observed cycle."""
    idx = frame.groupby(UNIT)[CYCLE].idxmax()
    return frame.loc[idx].reset_index(drop=True)
