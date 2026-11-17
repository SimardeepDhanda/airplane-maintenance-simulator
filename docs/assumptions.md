# Assumptions

Hypothetical assumptions the simulation relies on. Each later phase appends to this file.

## Data

| # | Assumption | Why |
|---|---|---|
| D1 | Only FD001 (one operating condition, one fault mode) is used until Phase 1 is validated. | Spec §3. Avoids mixing operating regimes. |
| D2 | C-MAPSS rows are 26 columns: unit, cycle, 3 operational settings, 21 sensors. | Verified on the files. The readme's "sensor measurement 26" is a numbering error. |
| D3 | Sensor columns are named `sensor_1`…`sensor_21` without physical meanings. | The dataset readme does not define them; spec §4 forbids inventing meanings. |
| D4 | C-MAPSS is simulated data, not airline telemetry. NASA unit IDs do not correspond to real aircraft. | Spec §1, §5. |

## Operations (fictional)

| # | Assumption | Why |
|---|---|---|
| O1 | Northstar Air, its tails, schedules, costs and resources are synthetic. | No real airline data is used. |
| O2 | One monitored engine per aircraft. Real narrowbodies have two or more. | Simplification (spec §5). |
| O3 | One flight leg consumes one engine cycle. | Simplification; cycles are not hours or distance. |
| O4 | The planning threshold is a user-set hypothetical policy, not a regulatory limit. | Spec §5, §6. |

## Modelling (Phase 1)

| # | Assumption | Why |
|---|---|---|
| M1 | Training RUL is capped at 125 cycles. | Early-life degradation is not observable from sensors; standard for C-MAPSS. Compared against uncapped in CV and test. |
| M2 | Model selection uses CV RMSE against capped truth, fixed before training. | Planning cares about engines near end of life. Uncapped metrics are reported alongside. |
| M3 | 20 of 100 training engines are held out for interval calibration. | Conformal calibration needs data the model never saw. |
| M4 | Interval coverage is reported, not guaranteed. | Cycles of one engine are dependent, which breaks exchangeability. |
| M5 | A channel with fewer than 3 distinct values among fit-engine rows is dropped. | Carries no usable signal. Rule uses fit engines only. |
