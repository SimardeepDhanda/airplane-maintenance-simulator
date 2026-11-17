"""Candidate regressors, from trivial baselines to gradient-boosted trees."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from sklearn.base import RegressorMixin
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from aerofleet_ml.data.load import CYCLE


@dataclass(frozen=True)
class Candidate:
    name: str
    description: str
    build: Callable[[int], RegressorMixin]


def _constant(_: int) -> RegressorMixin:
    return DummyRegressor(strategy="mean")


def _cycle_linear(_: int) -> RegressorMixin:
    # Uses only the observed cycle count: RUL ~ a + b * cycle.
    select_cycle = ColumnTransformer([("cycle", "passthrough", [CYCLE])], remainder="drop")
    return Pipeline([("select", select_cycle), ("model", LinearRegression())])


def _ridge(_: int) -> RegressorMixin:
    # The scaler is fitted inside the pipeline, i.e. only on the rows passed to fit().
    return Pipeline([("scale", StandardScaler()), ("model", Ridge(alpha=1.0))])


def _hgb(seed: int) -> RegressorMixin:
    return HistGradientBoostingRegressor(
        max_iter=300,
        learning_rate=0.05,
        max_leaf_nodes=15,
        min_samples_leaf=40,
        l2_regularization=1.0,
        early_stopping=False,
        random_state=seed,
    )


CANDIDATES: tuple[Candidate, ...] = (
    Candidate("constant", "Mean training RUL", _constant),
    Candidate("cycle_linear", "Linear regression on cycle count", _cycle_linear),
    Candidate("ridge", "Ridge regression on standardized features", _ridge),
    Candidate("hgb", "Histogram gradient boosting on features", _hgb),
)


def get_candidate(name: str) -> Candidate:
    for candidate in CANDIDATES:
        if candidate.name == name:
            return candidate
    raise KeyError(name)
