import math

import numpy as np
import pytest

from aerofleet_ml.evaluate import metrics


def test_rmse_mae_bias() -> None:
    assert metrics.rmse([0, 0], [3, -3]) == pytest.approx(3.0)
    assert metrics.mae([1, 2, 3], [2, 2, 5]) == pytest.approx(1.0)
    assert metrics.bias([10, 10], [12, 14]) == pytest.approx(3.0)


def test_phm08_score_matches_published_definition() -> None:
    # d = pred - true; early (d<0): exp(-d/13)-1, late (d>=0): exp(d/10)-1
    assert metrics.phm08_score([50], [50]) == 0.0
    assert metrics.phm08_score([50], [37]) == pytest.approx(math.e - 1)  # 13 cycles early
    assert metrics.phm08_score([50], [60]) == pytest.approx(math.e - 1)  # 10 cycles late
    assert metrics.phm08_score([50, 50], [60, 37]) == pytest.approx(2 * (math.e - 1))


def test_late_predictions_cost_more_than_early() -> None:
    assert metrics.phm08_score([50], [70]) > metrics.phm08_score([50], [30])


def test_by_rul_bin_groups_by_truth() -> None:
    rows = metrics.by_rul_bin(np.array([5, 30, 130]), np.array([5, 40, 125]))
    assert [r["true_rul"] for r in rows] == ["0-24", "25-49", "125+"]
    assert rows[1]["mae"] == pytest.approx(10.0)


@pytest.mark.parametrize(("t", "p"), [([], []), ([1, 2], [1])])
def test_invalid_shapes(t: list[float], p: list[float]) -> None:
    with pytest.raises(ValueError):
        metrics.rmse(t, p)
