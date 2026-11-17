"""Split conformal prediction intervals, calibrated on held-out engines.

Two one-sided quantiles (lower and upper tail, alpha/2 each) are estimated per predicted-RUL bin
("Mondrian" conformal). Separate tails handle the asymmetric errors of a capped-target model;
binning handles errors that grow with RUL.

Assumption: calibration and future residuals are exchangeable. Rows of the same engine are
temporally dependent, so the nominal level is not guaranteed. Empirical coverage on independent
held-out engines is reported instead of a guarantee.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike


@dataclass(frozen=True)
class ConformalCalibration:
    alpha: float
    bin_edges: tuple[float, ...]  # interior edges on predicted RUL; len = n_bins - 1
    lower_offsets: tuple[float, ...]  # per bin, subtracted from the point prediction
    upper_offsets: tuple[float, ...]  # per bin, added to the point prediction
    bin_counts: tuple[int, ...]

    def bin_index(self, y_pred: np.ndarray) -> np.ndarray:
        return np.searchsorted(np.asarray(self.bin_edges), y_pred, side="right")

    def interval(self, y_pred: ArrayLike) -> tuple[np.ndarray, np.ndarray]:
        p = np.asarray(y_pred, dtype=float)
        idx = self.bin_index(p)
        lower = p - np.asarray(self.lower_offsets)[idx]
        upper = p + np.asarray(self.upper_offsets)[idx]
        return np.maximum(lower, 0.0), upper


def _conformal_quantile(scores: np.ndarray, level: float) -> float:
    """Finite-sample split-conformal quantile: the ceil((n+1)*level)-th smallest score."""
    n = scores.size
    rank = math.ceil((n + 1) * level)
    if rank > n:
        return float("inf")
    return float(np.sort(scores)[rank - 1])


def calibrate(
    y_true: ArrayLike, y_pred: ArrayLike, alpha: float = 0.1, n_bins: int = 3
) -> ConformalCalibration:
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be in (0, 1)")
    t = np.asarray(y_true, dtype=float)
    p = np.asarray(y_pred, dtype=float)
    if t.shape != p.shape or t.size < n_bins * 20:
        raise ValueError("need at least 20 calibration rows per bin")
    edges = tuple(float(e) for e in np.quantile(p, np.linspace(0, 1, n_bins + 1)[1:-1]))
    idx = np.searchsorted(np.asarray(edges), p, side="right")
    level = 1.0 - alpha / 2.0
    lower, upper, counts = [], [], []
    for b in range(n_bins):
        mask = idx == b
        over = np.maximum(p[mask] - t[mask], 0.0)  # prediction above truth -> needs lower margin
        under = np.maximum(t[mask] - p[mask], 0.0)
        lower.append(_conformal_quantile(over, level))
        upper.append(_conformal_quantile(under, level))
        counts.append(int(mask.sum()))
    return ConformalCalibration(alpha, edges, tuple(lower), tuple(upper), tuple(counts))


def coverage(y_true: ArrayLike, lower: ArrayLike, upper: ArrayLike) -> dict[str, float]:
    t = np.asarray(y_true, dtype=float)
    lo = np.asarray(lower, dtype=float)
    hi = np.asarray(upper, dtype=float)
    return {
        "coverage": float(np.mean((t >= lo) & (t <= hi))),
        "lower_bound_coverage": float(np.mean(t >= lo)),
        "mean_width": float(np.mean(hi - lo)),
        "n": float(t.size),
    }
