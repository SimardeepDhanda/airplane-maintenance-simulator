"""End-to-end pipeline and inference on the synthetic fixture. Asserts structure and behaviour,
never performance numbers (synthetic metrics are meaningless)."""

import json
from pathlib import Path

import pandas as pd
import pytest

from aerofleet_ml.data.load import UNIT, load_subset
from aerofleet_ml.inference.predictor import InvalidHistoryError, Prediction, RulPredictor
from aerofleet_ml.pipeline import PipelineConfig, PipelineResult, run_pipeline

CONFIG = PipelineConfig(cv_folds=3, importance_repeats=2)


@pytest.fixture(scope="module")
def result(synthetic_dir: Path, tmp_path_factory: pytest.TempPathFactory) -> PipelineResult:
    return run_pipeline(synthetic_dir, tmp_path_factory.mktemp("artifacts"), CONFIG)


def test_artifacts_written_and_labelled_synthetic(result: PipelineResult) -> None:
    manifest = json.loads((result.artifact_dir / "manifest.json").read_text())
    assert manifest["data_kind"] == "synthetic_fixture"
    assert manifest["model_version"] == result.model_version
    assert (result.artifact_dir.parent / "LATEST").read_text().strip() == result.model_version
    assert set(manifest["split"]["fit_units"]).isdisjoint(manifest["split"]["calibration_units"])
    for key in ("schema_version", "dataset", "features", "conformal", "config", "environment"):
        assert key in manifest


def test_every_candidate_and_target_variant_evaluated(result: PipelineResult) -> None:
    cv = result.metrics["selection"]["results"]
    assert {(r["model"], r["target_cap"]) for r in cv} == {
        (m, c) for m in ("constant", "cycle_linear", "ridge", "hgb") for c in (125, None)
    }
    comparison = result.metrics["test"]["comparison"]
    assert sum(r["selected"] for r in comparison) == 1
    selected = result.metrics["selection"]["selected"]
    best_cv = min(cv, key=lambda r: r["rmse_vs_capped_truth"])
    assert (selected["model"], selected["target_cap"]) == (best_cv["model"], best_cv["target_cap"])


def test_pipeline_is_deterministic(
    synthetic_dir: Path, result: PipelineResult, tmp_path: Path
) -> None:
    again = run_pipeline(synthetic_dir, tmp_path, CONFIG)
    assert again.model_version == result.model_version
    for doc in (again.metrics, result.metrics):
        doc.pop("created_at", None)
    assert again.metrics == result.metrics


def test_test_split_untouched_by_calibration(synthetic_dir: Path, result: PipelineResult) -> None:
    manifest = json.loads((result.artifact_dir / "manifest.json").read_text())
    train, test = load_subset(synthetic_dir, "FD001")
    assert set(manifest["split"]["fit_units"]) | set(manifest["split"]["calibration_units"]) == set(
        train[UNIT]
    )
    assert result.metrics["test"]["n_engines"] == test[UNIT].nunique()


def test_predictor_round_trip_and_interface(synthetic_dir: Path, result: PipelineResult) -> None:
    predictor = RulPredictor.load(result.artifact_dir)
    _, test = load_subset(synthetic_dir, "FD001")
    history = test[test[UNIT] == 1].drop(columns="rul")
    prediction = predictor.predict(history)
    assert isinstance(prediction, Prediction)
    assert set(prediction.to_dict()) == {
        "rul_point",
        "rul_lower",
        "rul_upper",
        "model_version",
        "observed_through_cycle",
    }
    assert prediction.model_version == result.model_version
    assert prediction.observed_through_cycle == int(history["cycle"].max())
    assert 0 <= prediction.rul_lower <= prediction.rul_point <= prediction.rul_upper
    assert prediction.rul_point <= 125

    trajectory = predictor.predict_trajectory(history)
    assert len(trajectory) == len(history)
    assert trajectory[-1] == prediction
    # Prediction at cycle k equals prediction from a history truncated at k (no look-ahead).
    k = 20
    assert predictor.predict(history.iloc[:k]) == trajectory[k - 1]

    # Matches the evaluation output for the same engine.
    row = next(r for r in result.metrics["test"]["per_engine"] if r["unit_id"] == 1)
    assert row["rul_point"] == prediction.rul_point


def test_predictor_rejects_invalid_history(synthetic_dir: Path, result: PipelineResult) -> None:
    predictor = RulPredictor.load(result.artifact_dir)
    _, test = load_subset(synthetic_dir, "FD001")
    history = test[test[UNIT] == 1].drop(columns="rul")
    bad_inputs = {
        "missing columns": history.drop(columns="sensor_4"),
        "empty": history.iloc[0:0],
        "exactly one engine": test[test[UNIT].isin([1, 2])].drop(columns="rul"),
        "missing values": history.assign(sensor_4=float("nan")),
        "duplicate cycles": pd.concat([history, history.iloc[[0]]]),
    }
    for message, frame in bad_inputs.items():
        with pytest.raises(InvalidHistoryError, match=message):
            predictor.predict(frame)


def test_load_requires_artifact(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="make pipeline"):
        RulPredictor.load(tmp_path)
