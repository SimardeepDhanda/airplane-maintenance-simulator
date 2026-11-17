"""Causal feature engineering. Every feature at cycle t uses only rows with cycle <= t of the
same engine, so features never see the future and never mix engines."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from aerofleet_ml.data.load import CYCLE, UNIT

SENSOR_PREFIX = "sensor_"
SETTING_COLUMNS = ("setting_1", "setting_2", "setting_3")
# A channel with fewer distinct values than this in the training units carries no usable signal
# (FD001: sensors 1, 5, 10, 16, 18, 19 and setting_3 are constant; sensor_6 takes two values).
MIN_DISTINCT_VALUES = 3


@dataclass(frozen=True)
class FeatureSpec:
    sensors: tuple[str, ...]
    settings: tuple[str, ...]
    window: int = 10
    baseline_cycles: int = 10

    def columns(self) -> list[str]:
        cols = [CYCLE, *self.settings]
        for sensor in self.sensors:
            cols += [
                sensor,
                f"{sensor}_mean{self.window}",
                f"{sensor}_std{self.window}",
                f"{sensor}_delta",
            ]
        return cols


def select_channels(train: pd.DataFrame, min_distinct: int = MIN_DISTINCT_VALUES) -> FeatureSpec:
    """Choose informative sensors/settings using training-unit rows only."""
    sensors = tuple(
        c
        for c in train.columns
        if c.startswith(SENSOR_PREFIX) and train[c].nunique() >= min_distinct
    )
    settings = tuple(c for c in SETTING_COLUMNS if train[c].nunique() >= min_distinct)
    return FeatureSpec(sensors=sensors, settings=settings)


def build_features(frame: pd.DataFrame, spec: FeatureSpec) -> pd.DataFrame:
    """Feature matrix aligned with `frame`'s index. `frame` must be sorted by unit, cycle."""
    if not frame.equals(frame.sort_values([UNIT, CYCLE], kind="stable")):
        raise ValueError("frame must be sorted by unit_id, cycle")
    grouped = frame.groupby(UNIT, sort=False)
    out = pd.DataFrame(index=frame.index)
    out[CYCLE] = frame[CYCLE].astype("float64")
    for setting in spec.settings:
        out[setting] = frame[setting]
    for sensor in spec.sensors:
        series = grouped[sensor]
        out[sensor] = frame[sensor]
        out[f"{sensor}_mean{spec.window}"] = series.transform(
            lambda s: s.rolling(spec.window, min_periods=1).mean()
        )
        out[f"{sensor}_std{spec.window}"] = series.transform(
            lambda s: s.rolling(spec.window, min_periods=2).std().fillna(0.0)
        )
        # Drift from this engine's own early-life level (mean of its first k cycles seen so far).
        early = series.transform(
            lambda s: s.where(np.arange(len(s)) < spec.baseline_cycles).expanding().mean()
        )
        out[f"{sensor}_delta"] = out[f"{sensor}_mean{spec.window}"] - early
    return out[spec.columns()]
