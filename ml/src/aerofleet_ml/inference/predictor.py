"""Versioned inference interface.

    predictor = RulPredictor.load(artifact_dir)
    predictor.predict(engine_history) -> Prediction

`engine_history` is one engine's C-MAPSS rows (unit_id, cycle, settings, sensors) up to the
prediction cycle. Only those rows are used, so a prediction never depends on later observations.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.base import RegressorMixin

from aerofleet_ml.data.cmapss import COLUMNS
from aerofleet_ml.data.load import CYCLE, UNIT
from aerofleet_ml.evaluate.conformal import ConformalCalibration
from aerofleet_ml.features.build import FeatureSpec, build_features

MODEL_FILE = "model.joblib"
MANIFEST_FILE = "manifest.json"


class InvalidHistoryError(ValueError):
    """The supplied engine history cannot be used for prediction."""


@dataclass(frozen=True)
class Prediction:
    rul_point: float
    rul_lower: float
    rul_upper: float
    model_version: str
    observed_through_cycle: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RulPredictor:
    model: RegressorMixin
    spec: FeatureSpec
    calibration: ConformalCalibration
    model_version: str
    target_cap: int | None

    def _validate(self, history: pd.DataFrame) -> pd.DataFrame:
        missing = [c for c in COLUMNS if c not in history.columns]
        if missing:
            raise InvalidHistoryError(f"missing columns: {missing}")
        if history.empty:
            raise InvalidHistoryError("history is empty")
        if history[UNIT].nunique() != 1:
            raise InvalidHistoryError("history must contain exactly one engine")
        if history[list(COLUMNS)].isna().any().any():
            raise InvalidHistoryError("history contains missing values")
        ordered = history.sort_values(CYCLE, kind="stable").reset_index(drop=True)
        if ordered[CYCLE].duplicated().any():
            raise InvalidHistoryError("duplicate cycles in history")
        return ordered[list(COLUMNS)]

    def _point(self, features: pd.DataFrame) -> np.ndarray:
        raw = np.asarray(self.model.predict(features), dtype=float)
        upper = float(self.target_cap) if self.target_cap is not None else np.inf
        return np.clip(raw, 0.0, upper)

    def predict(self, history: pd.DataFrame) -> Prediction:
        return self.predict_trajectory(history)[-1]

    def predict_trajectory(self, history: pd.DataFrame) -> list[Prediction]:
        """Prediction at every observed cycle, each using only rows up to that cycle."""
        ordered = self._validate(history)
        features = build_features(ordered, self.spec)
        point = self._point(features)
        lower, upper = self.calibration.interval(point)
        cycles = ordered[CYCLE].to_numpy()
        return [
            Prediction(
                rul_point=round(float(p), 2),
                rul_lower=round(float(lo), 2),
                rul_upper=round(float(hi), 2),
                model_version=self.model_version,
                observed_through_cycle=int(c),
            )
            for p, lo, hi, c in zip(point, lower, upper, cycles, strict=True)
        ]

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, directory / MODEL_FILE)

    @classmethod
    def load(cls, directory: Path) -> RulPredictor:
        path = directory / MODEL_FILE
        if not path.is_file():
            raise FileNotFoundError(f"{path} not found. Run `make pipeline` to train a model.")
        obj = joblib.load(path)
        if not isinstance(obj, cls):
            raise TypeError(f"{path} does not contain a RulPredictor")
        manifest = json.loads((directory / MANIFEST_FILE).read_text())
        if manifest.get("model_version") != obj.model_version:
            raise ValueError("model file and manifest disagree on model_version")
        return obj
