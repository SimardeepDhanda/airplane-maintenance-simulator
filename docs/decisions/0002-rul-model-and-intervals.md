# ADR 0002: RUL model, selection and intervals

- **Status:** accepted (Phase 1)
- **Date:** 2026-11-17

## Decision

- Engine-level split: 80 fit / 20 calibration training engines. The official test split is used once,
  for reporting, after every choice is fixed.
- Candidates: constant, linear-on-cycle, Ridge, HistGradientBoosting; each with capped (125) and
  uncapped targets. Selected by grouped 5-fold CV RMSE against capped truth.
- Causal hand-built features (rolling mean/std, drift from early-life level) instead of a sequence model.
- Intervals: split conformal with separate lower/upper tails per predicted-RUL tertile, calibrated
  against true uncapped RUL.
- Artifact = joblib'd `RulPredictor` (model, feature spec, calibration, version) + JSON manifest and
  metrics. Only JSON is committed; CI regenerates and compares.

## Alternatives considered

- **LSTM/GRU:** optional per spec. Not attempted: the tree model's CV error (9.1 RMSE) leaves little room,
  and it would add PyTorch to the image.
- **Symmetric conformal (|residual|):** a capped model errs asymmetrically (true RUL can far exceed
  125), so a symmetric band would be needlessly wide on the lower side used for planning.
- **Quantile regression:** gives intervals without held-out calibration, but with no finite-sample
  argument. Conformal plus measured coverage is more defensible.
