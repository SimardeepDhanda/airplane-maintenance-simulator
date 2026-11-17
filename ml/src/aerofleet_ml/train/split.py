"""Engine-level partitioning. Rows of one engine never appear in more than one partition."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from aerofleet_ml.data.load import UNIT


@dataclass(frozen=True)
class UnitSplit:
    fit_units: tuple[int, ...]
    calibration_units: tuple[int, ...]

    def __post_init__(self) -> None:
        overlap = set(self.fit_units) & set(self.calibration_units)
        if overlap:
            raise ValueError(f"units in both partitions: {sorted(overlap)}")


def split_units(train: pd.DataFrame, calibration_fraction: float, seed: int) -> UnitSplit:
    if not 0.0 < calibration_fraction < 1.0:
        raise ValueError("calibration_fraction must be in (0, 1)")
    units = np.array(sorted(train[UNIT].unique()))
    n_cal = max(1, round(len(units) * calibration_fraction))
    if n_cal >= len(units):
        raise ValueError("not enough units to split")
    shuffled = np.random.default_rng(seed).permutation(units)
    return UnitSplit(
        fit_units=tuple(sorted(int(u) for u in shuffled[n_cal:])),
        calibration_units=tuple(sorted(int(u) for u in shuffled[:n_cal])),
    )
