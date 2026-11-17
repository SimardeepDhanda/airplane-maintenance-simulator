"""End-to-end training pipeline: load -> split by engine -> select model by grouped CV ->
calibrate intervals on held-out engines -> evaluate once on the official test split -> save.

The official test split is never used for selection or tuning.
"""

from __future__ import annotations

import hashlib
import json
import platform
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import sklearn
from sklearn.base import RegressorMixin
from sklearn.inspection import permutation_importance
from sklearn.model_selection import GroupKFold

from aerofleet_ml.data.cmapss import COLUMNS, DatasetError
from aerofleet_ml.data.load import CYCLE, TARGET, UNIT, last_cycle_rows, load_subset
from aerofleet_ml.evaluate import metrics
from aerofleet_ml.evaluate.conformal import calibrate, coverage
from aerofleet_ml.features.build import build_features, select_channels
from aerofleet_ml.inference.predictor import MANIFEST_FILE, RulPredictor
from aerofleet_ml.train.models import CANDIDATES, get_candidate
from aerofleet_ml.train.split import split_units

SCHEMA_VERSION = "cmapss-26col-v1"
METRICS_FILE = "metrics.json"
LATEST_FILE = "LATEST"


@dataclass(frozen=True)
class PipelineConfig:
    subset: str = "FD001"
    seed: int = 42
    target_cap: int = 125
    alpha: float = 0.1
    cv_folds: int = 5
    calibration_fraction: float = 0.2
    conformal_bins: int = 3
    importance_repeats: int = 5
    trajectory_units: int = 4
    selection_metric: str = "rmse_vs_capped_truth"


@dataclass
class PipelineResult:
    model_version: str
    artifact_dir: Path
    metrics: dict[str, Any] = field(repr=False)


def _target(y: pd.Series, cap: int | None) -> np.ndarray:
    values: np.ndarray = y.to_numpy(dtype=float)
    return np.minimum(values, float(cap)) if cap is not None else values


def _clip(pred: np.ndarray, cap: int | None) -> np.ndarray:
    clipped: np.ndarray = np.clip(pred, 0.0, float(cap) if cap is not None else np.inf)
    return clipped


def _scores(y_true: pd.Series, pred: np.ndarray, cap: int) -> dict[str, float]:
    return {
        "rmse": metrics.rmse(y_true, pred),
        "mae": metrics.mae(y_true, pred),
        "rmse_vs_capped_truth": metrics.rmse(_target(y_true, cap), pred),
        "mae_vs_capped_truth": metrics.mae(_target(y_true, cap), pred),
        "bias": metrics.bias(y_true, pred),
        "phm08_score": metrics.phm08_score(y_true, pred),
    }


def _read_source(dataset_dir: Path) -> dict[str, Any]:
    path = dataset_dir / "SOURCE.json"
    if not path.is_file():
        raise DatasetError(f"{path} missing; acquire the dataset with `make data`")
    source: dict[str, Any] = json.loads(path.read_text())
    return source


def _version(config: PipelineConfig, model_name: str, source: dict[str, Any]) -> str:
    payload = json.dumps(
        {
            "config": asdict(config),
            "model": model_name,
            "files": {k: v for k, v in source["files"].items() if config.subset in k},
            "sklearn": sklearn.__version__,
        },
        sort_keys=True,
    )
    digest = hashlib.sha256(payload.encode()).hexdigest()[:8]
    return f"{config.subset.lower()}-{model_name}-{digest}"


def run_pipeline(
    dataset_dir: Path, output_root: Path, config: PipelineConfig | None = None
) -> PipelineResult:
    cfg = config or PipelineConfig()
    source = _read_source(dataset_dir)
    data_kind = "synthetic_fixture" if source.get("synthetic") else "nasa_cmapss"
    train, test = load_subset(dataset_dir, cfg.subset)

    # 1. Engine-level split. Channel selection uses fit units only.
    split = split_units(train, cfg.calibration_fraction, cfg.seed)
    fit = train[train[UNIT].isin(split.fit_units)].reset_index(drop=True)
    cal = train[train[UNIT].isin(split.calibration_units)].reset_index(drop=True)
    spec = select_channels(fit)
    dropped = [c for c in COLUMNS[2:] if c not in spec.sensors + spec.settings]

    x_fit, x_cal = build_features(fit, spec), build_features(cal, spec)
    x_test = build_features(test, spec)

    # 2. Model selection: grouped CV over fit units, capped vs uncapped targets.
    cv = GroupKFold(n_splits=cfg.cv_folds)
    cv_results: list[dict[str, Any]] = []
    for candidate in CANDIDATES:
        for cap in (cfg.target_cap, None):
            oof = np.zeros(len(fit))
            for train_idx, val_idx in cv.split(x_fit, groups=fit[UNIT]):
                model = candidate.build(cfg.seed)
                model.fit(x_fit.iloc[train_idx], _target(fit[TARGET].iloc[train_idx], cap))
                oof[val_idx] = _clip(np.asarray(model.predict(x_fit.iloc[val_idx])), cap)
            cv_results.append(
                {
                    "model": candidate.name,
                    "target_cap": cap,
                    **_scores(fit[TARGET], oof, cfg.target_cap),
                }
            )
    best = min(cv_results, key=lambda r: r[cfg.selection_metric])
    best_cap: int | None = best["target_cap"]
    best_name: str = best["model"]

    # 3. Refit every candidate on all fit units (test comparison table), keep the selected one.
    fitted: dict[tuple[str, int | None], RegressorMixin] = {}
    for row in cv_results:
        key = (row["model"], row["target_cap"])
        model = get_candidate(row["model"]).build(cfg.seed)
        model.fit(x_fit, _target(fit[TARGET], row["target_cap"]))
        fitted[key] = model
    selected = fitted[(best_name, best_cap)]

    # 4. Conformal calibration on held-out engines, against true (uncapped) RUL.
    cal_pred = _clip(np.asarray(selected.predict(x_cal)), best_cap)
    calibration = calibrate(cal[TARGET], cal_pred, alpha=cfg.alpha, n_bins=cfg.conformal_bins)
    model_version = _version(cfg, best_name, source)
    predictor = RulPredictor(selected, spec, calibration, model_version, best_cap)

    # 5. Final evaluation on the official test split (once, after all choices are fixed).
    last_idx = test.groupby(UNIT)[CYCLE].idxmax().to_numpy()
    test_last = test.loc[last_idx]
    comparison = []
    for (name, cap), model in fitted.items():
        pred_all = _clip(np.asarray(model.predict(x_test)), cap)
        comparison.append(
            {
                "model": name,
                "target_cap": cap,
                "selected": (name, cap) == (best_name, best_cap),
                "last_cycle": _scores(test_last[TARGET], pred_all[last_idx], cfg.target_cap),
                "all_cycles": _scores(test[TARGET], pred_all, cfg.target_cap),
            }
        )
    point_all = _clip(np.asarray(selected.predict(x_test)), best_cap)
    lower_all, upper_all = calibration.interval(point_all)
    point_last, lower_last, upper_last = (
        point_all[last_idx],
        lower_all[last_idx],
        upper_all[last_idx],
    )

    per_engine = [
        {
            "unit_id": int(u),
            "observed_cycles": int(c),
            "true_rul": int(t),
            "rul_point": round(float(p), 2),
            "rul_lower": round(float(lo), 2),
            "rul_upper": round(float(hi), 2),
        }
        for u, c, t, p, lo, hi in zip(
            test_last[UNIT],
            test_last[CYCLE],
            test_last[TARGET],
            point_last,
            lower_last,
            upper_last,
            strict=True,
        )
    ]
    # Trajectories for engines spanning the range of true final RUL (deterministic choice).
    by_rul = test_last.sort_values([TARGET, UNIT])[UNIT].to_numpy()
    picks = sorted(
        {
            int(by_rul[i])
            for i in np.linspace(0, len(by_rul) - 1, cfg.trajectory_units).round().astype(int)
        }
    )
    trajectories = []
    for unit in picks:
        mask = (test[UNIT] == unit).to_numpy()
        trajectories.append(
            {
                "unit_id": unit,
                "cycle": test.loc[mask, CYCLE].astype(int).tolist(),
                "true_rul": test.loc[mask, TARGET].astype(int).tolist(),
                "rul_point": np.round(point_all[mask], 2).tolist(),
                "rul_lower": np.round(lower_all[mask], 2).tolist(),
                "rul_upper": np.round(upper_all[mask], 2).tolist(),
            }
        )

    importance = permutation_importance(
        selected,
        x_cal,
        _target(cal[TARGET], best_cap),
        scoring="neg_root_mean_squared_error",
        n_repeats=cfg.importance_repeats,
        random_state=cfg.seed,
    )
    order = np.argsort(-importance.importances_mean, kind="stable")
    importances = [
        {
            "feature": str(x_cal.columns[i]),
            "mean": float(importance.importances_mean[i]),
            "std": float(importance.importances_std[i]),
        }
        for i in order
    ]

    created_at = datetime.now(UTC).isoformat(timespec="seconds")
    metrics_doc: dict[str, Any] = {
        "model_version": model_version,
        "data_kind": data_kind,
        "subset": cfg.subset,
        "created_at": created_at,
        "units": {"rul": "engine cycles"},
        "selection": {
            "metric": cfg.selection_metric,
            "cv": f"GroupKFold({cfg.cv_folds}) over {len(split.fit_units)} fit engines",
            "results": cv_results,
            "selected": {"model": best_name, "target_cap": best_cap},
        },
        "test": {
            "evaluated_once": True,
            "n_engines": len(test_last),
            "n_rows": len(test),
            "comparison": comparison,
            "selected_by_true_rul_bin": metrics.by_rul_bin(test_last[TARGET], point_last),
            "intervals": {
                "nominal_coverage": 1 - cfg.alpha,
                "last_cycle": coverage(test_last[TARGET], lower_last, upper_last),
                "all_cycles": coverage(test[TARGET], lower_all, upper_all),
            },
            "per_engine": per_engine,
            "trajectories": trajectories,
        },
        "permutation_importance": {
            "data": f"{len(split.calibration_units)} calibration engines",
            "scoring": "RMSE increase when a feature is shuffled",
            "features": importances,
        },
    }
    manifest = {
        "model_version": model_version,
        "created_at": created_at,
        "data_kind": data_kind,
        "subset": cfg.subset,
        "schema_version": SCHEMA_VERSION,
        "dataset": {
            "archive_sha256": source.get("archive_sha256"),
            "files": {k: v for k, v in source["files"].items() if cfg.subset in k},
        },
        "config": asdict(cfg),
        "target": {
            "definition": "max_cycle - cycle (train); RUL file + offset (test)",
            "cap": best_cap,
        },
        "split": {
            "strategy": "by unit_id; seeded permutation",
            "fit_units": list(split.fit_units),
            "calibration_units": list(split.calibration_units),
        },
        "features": {
            "columns": spec.columns(),
            "sensors": list(spec.sensors),
            "settings": list(spec.settings),
            "dropped_channels": dropped,
            "drop_rule": "fewer than 3 distinct values in fit-unit rows",
            "window": spec.window,
            "baseline_cycles": spec.baseline_cycles,
        },
        "model": {
            "name": best_name,
            "params": {k: v for k, v in selected.get_params(deep=False).items() if _jsonable(v)},
        },
        "conformal": asdict(calibration),
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "sklearn": sklearn.__version__,
        },
    }

    artifact_dir = output_root / model_version
    predictor.save(artifact_dir)
    (artifact_dir / MANIFEST_FILE).write_text(json.dumps(manifest, indent=2) + "\n")
    (artifact_dir / METRICS_FILE).write_text(json.dumps(_finite(metrics_doc), indent=2) + "\n")
    (output_root / LATEST_FILE).write_text(model_version + "\n")
    return PipelineResult(model_version, artifact_dir, metrics_doc)


def _jsonable(value: object) -> bool:
    return isinstance(value, str | int | float | bool) or value is None


def _finite(obj: Any) -> Any:
    """JSON has no Infinity; an infinite interval offset is written as null."""
    if isinstance(obj, float) and not np.isfinite(obj):
        return None
    if isinstance(obj, dict):
        return {k: _finite(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_finite(v) for v in obj]
    return obj


__all__ = ["PipelineConfig", "PipelineResult", "last_cycle_rows", "run_pipeline"]
