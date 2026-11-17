from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from aerofleet_ml.data.load import UNIT, load_subset
from aerofleet_ml.features.build import build_features, select_channels


@pytest.fixture(scope="module")
def train(synthetic_dir: Path) -> pd.DataFrame:
    return load_subset(synthetic_dir, "FD001")[0]


def test_constant_channels_are_dropped(train: pd.DataFrame) -> None:
    spec = select_channels(train)
    assert "setting_3" not in spec.settings
    assert set(spec.sensors) == {"sensor_2", "sensor_4", "sensor_7", "sensor_11", "sensor_12"}


def test_channel_selection_sees_only_given_rows(train: pd.DataFrame) -> None:
    subset = train[train[UNIT] <= 3].copy()
    subset["sensor_1"] = np.arange(len(subset), dtype=float)  # varies only in this subset
    assert "sensor_1" in select_channels(subset).sensors
    assert "sensor_1" not in select_channels(train).sensors


def test_features_do_not_use_future_rows(train: pd.DataFrame) -> None:
    spec = select_channels(train)
    unit = train[train[UNIT] == 1].reset_index(drop=True)
    full = build_features(unit, spec)
    cut = 40
    truncated = build_features(unit.iloc[:cut].reset_index(drop=True), spec)
    pd.testing.assert_frame_equal(full.iloc[:cut], truncated)


def test_features_do_not_mix_engines(train: pd.DataFrame) -> None:
    spec = select_channels(train)
    both = train[train[UNIT].isin([1, 2])].reset_index(drop=True)
    alone = train[train[UNIT] == 2].reset_index(drop=True)
    joint = build_features(both, spec)
    second = joint[both[UNIT] == 2].reset_index(drop=True)
    pd.testing.assert_frame_equal(second, build_features(alone, spec))


def test_window_statistics_alignment(train: pd.DataFrame) -> None:
    spec = select_channels(train)
    unit = train[train[UNIT] == 1].reset_index(drop=True)
    features = build_features(unit, spec)
    s = unit["sensor_4"]
    assert features.loc[0, "sensor_4_mean10"] == pytest.approx(s.iloc[0])
    assert features.loc[0, "sensor_4_std10"] == 0.0
    assert features.loc[25, "sensor_4_mean10"] == pytest.approx(s.iloc[16:26].mean())
    assert features.loc[25, "sensor_4_std10"] == pytest.approx(s.iloc[16:26].std())
    early = s.iloc[:10].mean()
    assert features.loc[25, "sensor_4_delta"] == pytest.approx(s.iloc[16:26].mean() - early)
    assert features.loc[4, "sensor_4_delta"] == pytest.approx(s.iloc[:5].mean() - s.iloc[:5].mean())


def test_unsorted_input_is_rejected(train: pd.DataFrame) -> None:
    spec = select_channels(train)
    with pytest.raises(ValueError, match="sorted"):
        build_features(train.iloc[::-1], spec)


def test_no_missing_values(train: pd.DataFrame) -> None:
    features = build_features(train, select_channels(train))
    assert not features.isna().any().any()
    assert len(features) == len(train)
