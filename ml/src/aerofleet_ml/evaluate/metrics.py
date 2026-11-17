"""Regression metrics for RUL in cycles."""

from __future__ import annotations

from collections.abc import Sequence
from itertools import pairwise

import numpy as np
from numpy.typing import ArrayLike

RUL_BINS: tuple[float, ...] = (0, 25, 50, 75, 100, 125, np.inf)


def _arrays(y_true: ArrayLike, y_pred: ArrayLike) -> tuple[np.ndarray, np.ndarray]:
    t = np.asarray(y_true, dtype=float)
    p = np.asarray(y_pred, dtype=float)
    if t.shape != p.shape or t.ndim != 1:
        raise ValueError("y_true and y_pred must be 1-D arrays of equal length")
    if t.size == 0:
        raise ValueError("empty input")
    return t, p


def rmse(y_true: ArrayLike, y_pred: ArrayLike) -> float:
    t, p = _arrays(y_true, y_pred)
    return float(np.sqrt(np.mean((p - t) ** 2)))


def mae(y_true: ArrayLike, y_pred: ArrayLike) -> float:
    t, p = _arrays(y_true, y_pred)
    return float(np.mean(np.abs(p - t)))


def bias(y_true: ArrayLike, y_pred: ArrayLike) -> float:
    """Mean (prediction - truth). Positive means RUL is over-estimated (late, the riskier side)."""
    t, p = _arrays(y_true, y_pred)
    return float(np.mean(p - t))


def phm08_score(y_true: ArrayLike, y_pred: ArrayLike) -> float:
    """PHM08 challenge scoring function (Saxena et al., 2008), lower is better.

    d = predicted - true. s = sum(exp(-d/13) - 1) for d < 0, sum(exp(d/10) - 1) for d >= 0.
    Late predictions (d > 0) are penalised more heavily than early ones.
    """
    t, p = _arrays(y_true, y_pred)
    d = p - t
    return float(np.sum(np.where(d < 0, np.exp(-d / 13.0) - 1.0, np.exp(d / 10.0) - 1.0)))


def summary(y_true: ArrayLike, y_pred: ArrayLike) -> dict[str, float]:
    return {
        "rmse": rmse(y_true, y_pred),
        "mae": mae(y_true, y_pred),
        "bias": bias(y_true, y_pred),
        "phm08_score": phm08_score(y_true, y_pred),
        "n": float(np.asarray(y_true).size),
    }


def by_rul_bin(
    y_true: ArrayLike, y_pred: ArrayLike, edges: Sequence[float] = RUL_BINS
) -> list[dict[str, float | str]]:
    t, p = _arrays(y_true, y_pred)
    rows: list[dict[str, float | str]] = []
    for lo, hi in pairwise(edges):
        mask = (t >= lo) & (t < hi)
        if not mask.any():
            continue
        label = f"{int(lo)}+" if np.isinf(hi) else f"{int(lo)}-{int(hi) - 1}"
        rows.append(
            {
                "true_rul": label,
                "n": int(mask.sum()),
                "rmse": rmse(t[mask], p[mask]),
                "mae": mae(t[mask], p[mask]),
                "bias": bias(t[mask], p[mask]),
            }
        )
    return rows
