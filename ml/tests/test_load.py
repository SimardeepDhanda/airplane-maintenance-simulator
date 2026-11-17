from pathlib import Path

import pandas as pd
import pytest

from aerofleet_ml.data.cmapss import COLUMNS, DatasetError
from aerofleet_ml.data.load import (
    TARGET,
    add_test_targets,
    add_train_targets,
    last_cycle_rows,
    load_subset,
)


def _frame(units_cycles: dict[int, int]) -> pd.DataFrame:
    rows = [
        {**dict.fromkeys(COLUMNS, 0.0), "unit_id": u, "cycle": c}
        for u, n in units_cycles.items()
        for c in range(1, n + 1)
    ]
    return pd.DataFrame(rows, columns=list(COLUMNS))


def test_train_target_is_cycles_until_last_cycle() -> None:
    out = add_train_targets(_frame({1: 4, 2: 2}))
    assert out[TARGET].tolist() == [3, 2, 1, 0, 1, 0]


def test_test_target_adds_offset_from_final_rul() -> None:
    out = add_test_targets(_frame({1: 3, 2: 2}), pd.Series({1: 10, 2: 5}))
    assert out[TARGET].tolist() == [12, 11, 10, 6, 5]


def test_test_target_requires_every_unit() -> None:
    with pytest.raises(DatasetError, match="No final RUL"):
        add_test_targets(_frame({1: 2, 2: 2}), pd.Series({1: 10}))


def test_last_cycle_rows_one_per_unit() -> None:
    last = last_cycle_rows(add_train_targets(_frame({1: 4, 2: 2})))
    assert last[["unit_id", "cycle", TARGET]].values.tolist() == [[1, 4, 0], [2, 2, 0]]


def test_load_subset_maps_rul_file_lines_to_units(synthetic_dir: Path) -> None:
    train, test = load_subset(synthetic_dir, "FD001")
    final = last_cycle_rows(test).set_index("unit_id")[TARGET]
    expected = [int(v) for v in (synthetic_dir / "RUL_FD001.txt").read_text().split()]
    assert final.tolist() == expected
    assert (train.groupby("unit_id")[TARGET].min() == 0).all()
    assert list(train.columns) == [*COLUMNS, TARGET]
