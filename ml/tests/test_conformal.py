import numpy as np
import pytest

from aerofleet_ml.evaluate.conformal import calibrate, coverage


def _heteroscedastic(n: int, seed: int) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    pred = rng.uniform(0, 125, n)
    truth = pred + rng.normal(0, 2 + pred / 10, n)  # errors grow with RUL
    return truth, pred


def test_intervals_contain_point_and_are_non_negative() -> None:
    truth, pred = _heteroscedastic(600, 0)
    cal = calibrate(truth, pred, alpha=0.1)
    lower, upper = cal.interval(pred)
    assert np.all(lower <= pred + 1e-9) and np.all(pred <= upper)
    assert np.all(lower >= 0)


def test_empirical_coverage_near_nominal_on_exchangeable_data() -> None:
    cal = calibrate(*_heteroscedastic(3000, 1), alpha=0.1)
    truth, pred = _heteroscedastic(20000, 2)
    result = coverage(truth, *cal.interval(pred))
    assert 0.88 <= result["coverage"] <= 0.93


def test_binning_adapts_width_to_error_scale() -> None:
    cal = calibrate(*_heteroscedastic(3000, 3), alpha=0.1, n_bins=3)
    widths = np.add(cal.lower_offsets, cal.upper_offsets)
    assert widths[0] < widths[1] < widths[2]


def test_smaller_alpha_gives_wider_intervals() -> None:
    truth, pred = _heteroscedastic(1000, 4)
    w90 = coverage(truth, *calibrate(truth, pred, alpha=0.1).interval(pred))["mean_width"]
    w80 = coverage(truth, *calibrate(truth, pred, alpha=0.2).interval(pred))["mean_width"]
    assert w90 > w80


def test_rejects_too_few_rows() -> None:
    with pytest.raises(ValueError, match="calibration rows"):
        calibrate([1.0] * 10, [1.0] * 10)


def test_too_few_scores_gives_unbounded_offset() -> None:
    truth, pred = _heteroscedastic(60, 5)
    cal = calibrate(truth, pred, alpha=0.01, n_bins=3)  # 20 rows/bin cannot support 99.5%
    assert np.isinf(cal.upper_offsets).all()
