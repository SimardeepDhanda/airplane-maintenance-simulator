# Data dictionary

## C-MAPSS rows (`train_FD00x.txt`, `test_FD00x.txt`)

Whitespace-delimited, 26 numeric columns, one row per engine per operational cycle.

| Column | Meaning (per dataset readme) | Used in FD001 model |
|---|---|---|
| `unit_id` | Engine identifier within the file | grouping only |
| `cycle` | Operational cycle index, starts at 1 | yes (feature) |
| `setting_1`, `setting_2` | Operational settings | yes |
| `setting_3` | Operational setting (constant in FD001) | dropped |
| `sensor_1` … `sensor_21` | Sensor measurements, noisy. Physical meanings are not given in the readme. | 14 kept; 1, 5, 6, 10, 16, 18, 19 dropped |

`RUL_FD00x.txt`: one integer per line; line *i* is the true RUL after the last row of test unit *i*.

## Derived

| Name | Definition |
|---|---|
| `rul` | Cycles to simulated failure. Train: `max_cycle − cycle`. Test: `RUL_file + (last_cycle − cycle)` |
| `sensor_k_mean10` | Mean of the engine's last ≤10 readings, including the current one |
| `sensor_k_std10` | Sample standard deviation of the same window (0 with one reading) |
| `sensor_k_delta` | `sensor_k_mean10` minus the mean of the engine's first ≤10 readings |

## Model outputs (`predict()`)

| Field | Unit | Meaning |
|---|---|---|
| `rul_point` | cycles | Point estimate, clipped to [0, 125] |
| `rul_lower`, `rul_upper` | cycles | Conformal interval, nominal 90%, not guaranteed (see model card) |
| `model_version` | – | Artifact id, e.g. `fd001-hgb-3a2ffab7` |
| `observed_through_cycle` | cycle | Last cycle of history used |
