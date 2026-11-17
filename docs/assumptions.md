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
| O5 | 6 stations (real IATA codes): hubs ORD and DEN (maintenance bases), plus ATL, BOS, PHX, SEA. Hub-and-spoke routing. | Small, geographically plausible network. PHX (no DST) exercises timezone handling. |
| O6 | Block time = 35 min + great-circle distance at 450 mph, rounded up to 5 min. | Simple, monotonic in distance. |
| O7 | Minimum turn 45 min + 0–60 min seeded slack. Departures 06:00–21:30 local. Aircraft overnight where their day ends. | Plausible narrowbody rotations without curfew modelling. |
| O8 | Schedule week starts 2027-03-11 10:00 UTC and spans the US DST change (2027-03-14). All aircraft start at their home hub. | Fixed date makes runs reproducible and exercises DST. |
| O9 | Ships 801–820 are fleet numbers, not registrations. Engine `ENG-8xx` is mapped to one NASA FD001 *test* engine, chosen by seeded pick across the model's predicted-RUL range (never by ground truth). | Avoids real tail numbers; gives a realistic mix; test engines were never used to train the model. |
| O10 | A NASA engine's last observed cycle is "now" (the simulation start). | C-MAPSS has no calendar time. |
| O11 | Planning status: `critical` if forecast legs exceed the lower bound (L − n < 0); `review` if L − n is below the buffer; else `ok`. Default buffer 10 cycles. | Spec §5 planning flags. |

## Modelling (Phase 1)

| # | Assumption | Why |
|---|---|---|
| M1 | Training RUL is capped at 125 cycles. | Early-life degradation is not observable from sensors; standard for C-MAPSS. Compared against uncapped in CV and test. |
| M2 | Model selection uses CV RMSE against capped truth, fixed before training. | Planning cares about engines near end of life. Uncapped metrics are reported alongside. |
| M3 | 20 of 100 training engines are held out for interval calibration. | Conformal calibration needs data the model never saw. |
| M4 | Interval coverage is reported, not guaranteed. | Cycles of one engine are dependent, which breaks exchangeability. |
| M5 | A channel with fewer than 3 distinct values among fit-engine rows is dropped. | Carries no usable signal. Rule uses fit engines only. |
