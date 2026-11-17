# Model card: `fd001-hgb-3a2ffab7`

Remaining-useful-life (RUL) regressor for NASA C-MAPSS FD001. All numbers below were produced by
`make pipeline` and are stored in `ml/artifacts/fd001-hgb-3a2ffab7/metrics.json`. CI re-runs the
pipeline on the real data and fails if they do not reproduce.

**Not for operational use.** RUL here means *estimated cycles to simulated failure* in a NASA
simulation. It is not an airworthiness determination, a maintenance limit or a clearance decision.

## Data

| | |
|---|---|
| Source | NASA PCoE entry 6, *Turbofan Engine Degradation Simulation* (C-MAPSS), FD001 ([provenance](data_provenance.md)) |
| Nature | Simulated turbofan run-to-failure data, one operating condition, one fault mode (HPC degradation) |
| Train | 100 engines, 20,631 cycles, each run to failure |
| Test (official) | 100 engines, 13,096 cycles, truncated before failure; true RUL at last cycle from `RUL_FD001.txt` |
| Fit / calibration | 80 / 20 training engines, seeded permutation by `unit_id` (seed 42) |

## Target

`RUL(i, t) = max_cycle(i) − t` for training engines. For test engines, `RUL_file(i) + (last_cycle(i) − t)`.
The selected model is trained on RUL capped at **125 cycles**. The cap encodes the common assumption
that degradation is not observable early in life: a prediction of ~125 means "no detectable
degradation yet", not "exactly 125 cycles left".

## Features (causal)

From 14 sensors and 2 operational settings. Dropped channels (fewer than 3 distinct values in
fit-engine rows): `setting_3`, sensors 1, 5, 6, 10, 16, 18, 19. Per sensor: current value, 10-cycle
rolling mean and standard deviation, and *delta* (rolling mean minus the engine's own mean over its
first 10 cycles). Plus the observed cycle count. Every feature at cycle t uses only that engine's rows
up to t (tested). Sensor names are NASA column indices; the dataset does not define physical meanings.

## Model selection

Grouped 5-fold CV over the 80 fit engines (no engine in both train and validation folds). Every model
is trained with capped and uncapped targets. Selection metric, fixed before training: CV RMSE against
true RUL capped at 125. The official test set played no part in any choice. Hyperparameters were set
once before the first run and not changed after seeing test results.

| CV (all cycles, 80 engines) | cap | RMSE vs capped truth |
|---|---|---|
| Constant (mean) | 125 | 41.61 |
| Linear on cycle | 125 | 28.23 |
| Ridge | 125 | 15.95 |
| **HistGradientBoosting** | **125** | **9.12** |
| HistGradientBoosting | none | 36.30 |

Selected: HistGradientBoosting (300 iterations, learning rate 0.05, 15 leaves, min 40 samples/leaf,
L2 1.0, no early stopping, seed 42), capped target.

## Test results (official FD001 test split, evaluated once)

Last observed cycle of each of the 100 test engines (the standard benchmark setting). Errors are
predicted − true, in cycles.

| Model | cap | RMSE | MAE | RMSE vs capped truth | Bias | PHM08 score |
|---|---|---|---|---|---|---|
| Constant (mean) | 125 | 43.24 | 35.91 | 42.13 | +11.93 | 35,723 |
| Linear on cycle | 125 | 33.52 | 27.78 | 32.48 | +3.33 | 5,820 |
| Ridge | 125 | 16.89 | 13.68 | 15.83 | +2.62 | 470 |
| **HistGradientBoosting** | **125** | **11.44** | **8.35** | **10.39** | **+0.09** | **200** |
| HistGradientBoosting | none | 25.02 | 15.37 | 26.63 | +9.95 | 197,406 |

The boosted model beats the Ridge baseline by 5.45 RMSE (32% lower) on the same engines.
Capping helps every model. PHM08 score follows Saxena et al. (2008); late predictions cost more.

Selected model by true RUL at last cycle:

| True RUL | n | RMSE | MAE | Bias |
|---|---|---|---|---|
| 0–24 | 19 | 3.50 | 2.93 | +1.28 |
| 25–49 | 11 | 3.75 | 2.62 | −1.06 |
| 50–74 | 13 | 9.60 | 6.69 | +3.38 |
| 75–99 | 23 | 14.62 | 11.47 | +7.22 |
| 100–124 | 23 | 12.11 | 9.39 | −1.33 |
| 125+ | 11 | 17.07 | 16.66 | −16.66 (cap) |

Accuracy is highest close to failure. The 75–99 band is over-estimated on average (late, the riskier side).

**All test cycles** (13,096 rows, targets derived per row): RMSE 54.07 against true RUL, 8.89 against
capped truth. The large uncapped error comes from early-life cycles whose true RUL (up to ~340) is
far above the 125 cap. This is expected behaviour of a capped model, not leakage.

## Prediction intervals

Split conformal, two one-sided tails (5% each) per predicted-RUL tertile, calibrated on the 20
held-out engines (3,852 rows) against true, uncapped RUL. Nominal level 90%.

| Held-out data | Coverage | Lower bound holds | Mean width |
|---|---|---|---|
| Test, last cycle (100 engines) | 90.0% | 94.0% | 43.9 cycles |
| Test, all cycles (13,096 rows) | 77.5% | 96.2% | 76.8 cycles |

Interval offsets (cycles below / above the point estimate): predicted < 67: −7.3 / +8.3;
67–121: −23.8 / +31.3; ≥ 121: −13.3 / +92.5.

Caveats: rows from one engine are temporally dependent, so calibration rows are not exchangeable and
the 90% level is not guaranteed. Coverage is near nominal at the last cycle, where test engines are
independent. Across all cycles the *upper* bound under-covers early-life rows, while the *lower*
bound (the side used for conservative planning margins) holds at 96%. Only 20 engines are used for
calibration, so the offsets are noisy.

## Model influence

Permutation importance on the calibration engines (RMSE increase when a feature is shuffled):
`sensor_11_delta` 5.16, `cycle` 4.87, `sensor_4_delta` 4.79, `sensor_14_delta` 3.92,
`sensor_9_delta` 3.62, `sensor_8_delta` 2.76, `sensor_15_delta` 1.99. This describes what the model
relies on. It does not identify physical causes or diagnose faults.

## Limitations

- FD001 only: one operating condition and one fault mode. FD002–FD004 need regime normalisation and are
  not supported.
- Predictions saturate at 125 cycles. Healthy engines all look alike.
- 100 training engines. Metrics on 100 test engines have sampling noise of a few cycles.
- No sequence model (LSTM/GRU). The spec makes it optional and earned only by validation gains; with
  CV RMSE of 9.1 for the tree model, it was not attempted.
- The version id hashes config, data checksums and scikit-learn version, not source code. Code changes
  that alter results must change the config or be caught by the reproducibility check in CI.

## Reproduce

```bash
make data && make pipeline      # ~20 s on a laptop
uv run pytest -m dataset        # re-runs and compares to the committed metrics
```

Artifacts: `ml/artifacts/<version>/{manifest.json, metrics.json}` (committed) and `model.joblib`
(gitignored; regenerate with `make pipeline`). `ml/artifacts/LATEST` names the current version.
