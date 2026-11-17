from pathlib import Path

import pytest

from aerofleet_ml.data.load import UNIT, load_subset
from aerofleet_ml.train.split import UnitSplit, split_units


def test_split_partitions_units_without_overlap(synthetic_dir: Path) -> None:
    train, _ = load_subset(synthetic_dir, "FD001")
    split = split_units(train, calibration_fraction=0.2, seed=1)
    all_units = set(train[UNIT].unique())
    assert set(split.fit_units) | set(split.calibration_units) == all_units
    assert not set(split.fit_units) & set(split.calibration_units)
    assert len(split.calibration_units) == round(len(all_units) * 0.2)


def test_split_is_seeded(synthetic_dir: Path) -> None:
    train, _ = load_subset(synthetic_dir, "FD001")
    assert split_units(train, 0.2, seed=3) == split_units(train, 0.2, seed=3)
    assert split_units(train, 0.2, seed=3) != split_units(train, 0.2, seed=4)


def test_overlapping_split_is_rejected() -> None:
    with pytest.raises(ValueError, match="both partitions"):
        UnitSplit(fit_units=(1, 2), calibration_units=(2, 3))


@pytest.mark.parametrize("fraction", [0.0, 1.0, -0.1])
def test_invalid_fraction(synthetic_dir: Path, fraction: float) -> None:
    train, _ = load_subset(synthetic_dir, "FD001")
    with pytest.raises(ValueError):
        split_units(train, fraction, seed=0)
