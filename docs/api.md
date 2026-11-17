# API

Base path `/api/v1`. Interactive docs at `/docs` (OpenAPI at `/openapi.json`). Responses below were captured from the seeded demo database (NASA FD001 engines, fictional schedule) and trimmed: lists show two items then `"…"`.

All errors use one envelope: `{"error": {"code", "message", "details"?}}`. Codes: `validation_error` (422), `naive_datetime` (422), `<kind>_not_found` (404), `not_seeded` (503).

`buffer` (cycles, 0–200, default `PLANNING_BUFFER_CYCLES`=10) is accepted by fleet, engine and flight routes and changes planning status and flight flags.

## Fleet summary

`GET /api/v1/fleet/summary`

Counts by planning status at the simulation start.

```json
{
  "as_of": "2027-03-11T10:00:00Z",
  "horizon_end": "2027-03-18T10:00:00Z",
  "aircraft": 20,
  "engines": 20,
  "flights": 555,
  "planning_buffer": 10,
  "status_counts": {
    "ok": 14,
    "review": 1,
    "critical": 5
  },
  "model": {
    "version": "fd001-hgb-3a2ffab7",
    "data_kind": "nasa_cmapss",
    "subset": "FD001",
    "trained_at": "2026-11-17T00:51:29Z"
  }
}
```

## Engines

`GET /api/v1/engines?status=critical&sort=conservative_margin&page_size=2`

Filters: `status` (repeatable), `aircraft_id`, `station`. Sort: `id`, `rul_point`, `rul_lower`, `conservative_margin`, `observed_cycles`; `order` asc/desc. Paginated (`page`, `page_size` ≤ 100).

```json
{
  "items": [
    {
      "id": "ENG-802",
      "aircraft_id": "802",
      "station": "DEN",
      "observed_cycles": 203,
      "prediction": {
        "rul_point": 5.61,
        "rul_lower": 0.0,
        "rul_upper": 13.88,
        "model_version": "fd001-hgb-3a2ffab7",
        "observed_through_cycle": 203
      },
      "planning": {
        "forecast_legs": 28,
        "forecast_cycles": 28,
        "margin": -22.39,
        "conservative_margin": -28.0,
        "status": "critical",
        "buffer": 10,
        "first_flagged_flight_id": "NS1010-20270311",
        "first_flagged_departure": "2027-03-11T13:25:00Z"
      }
    },
    {
      "id": "ENG-801",
      "aircraft_id": "801",
      "station": "ORD",
      "observed_cycles": 147,
      "prediction": {
        "rul_point": 15.07,
        "rul_lower": 7.82,
        "rul_upper": 23.33,
        "model_version": "fd001-hgb-3a2ffab7",
        "observed_through_cycle": 147
      },
      "planning": {
        "forecast_legs": 26,
        "forecast_cycles": 26,
        "margin": -10.93,
        "conservative_margin": -18.18,
        "status": "critical",
        "buffer": 10,
        "first_flagged_flight_id": "NS1000-20270311",
        "first_flagged_departure": "2027-03-11T12:25:00Z"
      }
    }
  ],
  "total": 5,
  "page": 1,
  "page_size": 2
}
```

## Engine detail

`GET /api/v1/engines/ENG-816`

Latest prediction, planning assessment, NASA provenance and every scheduled flight of the assigned aircraft. `eval_true_rul` is NASA ground truth, shown for evaluation only.

```json
{
  "id": "ENG-816",
  "aircraft_id": "816",
  "station": "DEN",
  "observed_cycles": 146,
  "prediction": {
    "rul_point": 37.8,
    "rul_lower": 30.55,
    "rul_upper": 46.07,
    "model_version": "fd001-hgb-3a2ffab7",
    "observed_through_cycle": 146
  },
  "planning": {
    "forecast_legs": 25,
    "forecast_cycles": 25,
    "margin": 12.8,
    "conservative_margin": 5.55,
    "status": "review",
    "buffer": 10,
    "first_flagged_flight_id": "NS1152-20270316",
    "first_flagged_departure": "2027-03-16T22:15:00Z"
  },
  "fleet_type": "Narrowbody (generic)",
  "home_base": "DEN",
  "provenance": {
    "dataset": "NASA C-MAPSS",
    "subset": "FD001",
    "split": "test",
    "unit_id": 46,
    "data_kind": "nasa_cmapss",
    "eval_true_rul": 47
  },
  "flights": [
    {
      "id": "NS1150-20270311",
      "flight_number": "NS1150",
      "aircraft_id": "816",
      "engine_id": "ENG-816",
      "origin": "DEN",
      "destination": "SEA",
      "departure": "2027-03-11T14:00:00Z",
      "arrival": "2027-03-11T16:55:00Z",
      "departure_local": "2027-03-11T07:00:00-07:00",
      "arrival_local": "2027-03-11T08:55:00-08:00",
      "origin_tz": "America/Denver",
      "destination_tz": "America/Los_Angeles",
      "origin_tz_abbr": "MST",
      "destination_tz_abbr": "PST",
      "status": "scheduled",
      "cycles": 1,
      "cumulative_cycles": 1,
      "conservative_margin_after": 29.55,
      "flagged": false
    },
    {
      "id": "NS1151-20270311",
      "flight_number": "NS1151",
      "aircraft_id": "816",
      "engine_id": "ENG-816",
      "origin": "SEA",
      "destination": "ORD",
      "departure": "2027-03-11T18:05:00Z",
      "arrival": "2027-03-11T22:30:00Z",
      "departure_local": "2027-03-11T10:05:00-08:00",
      "arrival_local": "2027-03-11T16:30:00-06:00",
      "origin_tz": "America/Los_Angeles",
      "destination_tz": "America/Chicago",
      "origin_tz_abbr": "PST",
      "destination_tz_abbr": "CST",
      "status": "scheduled",
      "cycles": 1,
      "cumulative_cycles": 2,
      "conservative_margin_after": 28.55,
      "flagged": false
    },
    "\u2026"
  ]
}
```

## Engine history

`GET /api/v1/engines/ENG-816/history?sensors=sensor_4&sensors=sensor_11`

Sensor series and the model's prediction at every observed cycle (each using only data up to that cycle). `sensors` repeatable; default all 21.

```json
{
  "engine_id": "ENG-816",
  "model_version": "fd001-hgb-3a2ffab7",
  "cycles": [
    1,
    2,
    "\u2026"
  ],
  "sensors": [
    {
      "name": "sensor_4",
      "values": [
        1397.15,
        1405.54,
        "\u2026"
      ]
    },
    {
      "name": "sensor_11",
      "values": [
        47.38,
        47.33,
        "\u2026"
      ]
    }
  ],
  "rul_point": [
    125.0,
    124.66,
    "\u2026"
  ],
  "rul_lower": [
    111.67,
    111.33,
    "\u2026"
  ],
  "rul_upper": [
    217.48,
    217.13,
    "\u2026"
  ]
}
```

## Flights

`GET /api/v1/flights?flagged=true&page_size=2`

Filters: `aircraft_id`, `engine_id`, `origin`, `destination`, `departure_from`/`departure_to` (UTC with offset), `flagged`. Paginated (`page`, `page_size` ≤ 1000; the full 7-day schedule fits one page). Local times carry the airport's offset and abbreviation.

```json
{
  "items": [
    {
      "id": "NS1000-20270311",
      "flight_number": "NS1000",
      "aircraft_id": "801",
      "engine_id": "ENG-801",
      "origin": "ORD",
      "destination": "ATL",
      "departure": "2027-03-11T12:25:00Z",
      "arrival": "2027-03-11T14:25:00Z",
      "departure_local": "2027-03-11T06:25:00-06:00",
      "arrival_local": "2027-03-11T09:25:00-05:00",
      "origin_tz": "America/Chicago",
      "destination_tz": "America/New_York",
      "origin_tz_abbr": "CST",
      "destination_tz_abbr": "EST",
      "status": "scheduled",
      "cycles": 1,
      "cumulative_cycles": 1,
      "conservative_margin_after": 6.82,
      "flagged": true
    },
    {
      "id": "NS1010-20270311",
      "flight_number": "NS1010",
      "aircraft_id": "802",
      "engine_id": "ENG-802",
      "origin": "DEN",
      "destination": "PHX",
      "departure": "2027-03-11T13:25:00Z",
      "arrival": "2027-03-11T15:25:00Z",
      "departure_local": "2027-03-11T06:25:00-07:00",
      "arrival_local": "2027-03-11T08:25:00-07:00",
      "origin_tz": "America/Denver",
      "destination_tz": "America/Phoenix",
      "origin_tz_abbr": "MST",
      "destination_tz_abbr": "MST",
      "status": "scheduled",
      "cycles": 1,
      "cumulative_cycles": 1,
      "conservative_margin_after": -1.0,
      "flagged": true
    }
  ],
  "total": 121,
  "page": 1,
  "page_size": 2
}
```

## Airports

`GET /api/v1/airports`

```json
[
  {
    "code": "ATL",
    "name": "Hartsfield-Jackson Atlanta International",
    "city": "Atlanta",
    "timezone": "America/New_York",
    "is_hub": false,
    "has_maintenance_base": false
  },
  {
    "code": "BOS",
    "name": "Boston Logan International",
    "city": "Boston",
    "timezone": "America/New_York",
    "is_hub": false,
    "has_maintenance_base": false
  },
  "\u2026"
]
```

## Model metrics

`GET /api/v1/models/metrics`

Measured evaluation of the active model, as written by the pipeline.

```json
{
  "model": {
    "version": "fd001-hgb-3a2ffab7",
    "data_kind": "nasa_cmapss",
    "subset": "FD001",
    "trained_at": "2026-11-17T00:51:29Z"
  },
  "selection": {
    "cv": "GroupKFold(5) over 80 fit engines",
    "metric": "rmse_vs_capped_truth",
    "results": [
      {
        "mae": 59.460563041550216,
        "bias": -22.577611120797968,
        "rmse": 74.17450073607313,
        "model": "constant",
        "target_cap": 125,
        "phm08_score": 25601780527.764248,
        "mae_vs_capped_truth": 36.88299584445863,
        "rmse_vs_capped_truth": 41.6131893047316
      },
      {
        "mae": 58.24855377255669,
        "bias": -8.029909428935685e-05,
        "rmse": 70.65623890577626,
        "model": "constant",
        "target_cap": null,
        "phm08_score": 4619604918.768094,
        "mae_vs_capped_truth": 35.670986575465086,
        "rmse_vs_capped_truth": 47.34368686155509
      },
      "\u2026"
    ],
    "selected": {
      "model": "hgb",
      "target_cap": 125
    }
  },
  "test": {
    "n_rows": 13096,
    "intervals": {
      "all_cycles": {
        "n": 13096.0,
        "coverage": 0.7749694563225412,
        "mean_width": 76.81951847475854,
        "lower_bound_coverage": 0.9620494807574832
      },
      "last_cycle": {
        "n": 100.0,
        "coverage": 0.9,
        "mean_width": 43.91879005391701,
        "lower_bound_coverage": 0.94
      },
      "nominal_coverage": 0.9
    },
    "n_engines": 100,
    "comparison": [
      {
        "model": "constant",
        "selected": false,
        "all_cycles": {
          "mae": 65.09075170704371,
          "bias": -53.78540342884316,
          "rmse": 79.8201594330399,
          "phm08_score": 6884314761.899294,
          "mae_vs_capped_truth": 32.77210479195512,
          "rmse_vs_capped_truth": 34.949022510917395
        },
        "last_cycle": {
          "mae": 35.90906132665832,
          "bias": 11.933066332916153,
          "rmse": 43.23502830004598,
          "phm08_score": 35722.89002116715,
          "mae_vs_capped_truth": 34.83906132665832,
          "rmse_vs_capped_truth": 42.13012264470895
        },
        "target_cap": 125
      },
      {
        "model": "constant",
        "selected": false,
        "all_cycles": {
          "mae": 53.18493955049624,
          "bias": -31.20783623175156,
          "rmse": 66.72568674940948,
          "phm08_score": 1215744790.6129913,
          "mae_vs_capped_truth": 20.86629263540766,
          "rmse_vs_capped_truth": 27.601565890760643
        },
        "last_cycle": {
          "mae": 41.833478753203416,
          "bias": 34.510633530007766,
          "rmse": 54.017158631702344,
          "phm08_score": 336290.4706040637,
          "mae_vs_capped_truth": 40.763478753203415,
          "rmse_vs_capped_truth": 53.58963502764981
        },
        "target_cap": null
      },
      "\u2026"
    ],
    "per_engine": [
      {
        "unit_id": 1,
        "true_rul": 112,
        "rul_lower": 93.99,
        "rul_point": 117.77,
        "rul_upper": 149.11,
        "observed_cycles": 31
      },
      {
        "unit_id": 2,
        "true_rul": 98,
        "rul_lower": 91.2,
        "rul_point": 114.98,
        "rul_upper": 146.32,
        "observed_cycles": 49
      },
      "\u2026"
    ],
    "trajectories": [
      {
        "cycle": [
          1,
          2,
          "\u2026"
        ],
        "unit_id": 25,
        "true_rul": [
          192,
          191,
          "\u2026"
        ],
        "rul_lower": [
          111.67,
          111.6,
          "\u2026"
        ],
        "rul_point": [
          125.0,
          124.93,
          "\u2026"
        ],
        "rul_upper": [
          217.48,
          217.41,
          "\u2026"
        ]
      },
      {
        "cycle": [
          1,
          2,
          "\u2026"
        ],
        "unit_id": 34,
        "true_rul": [
          209,
          208,
          "\u2026"
        ],
        "rul_lower": [
          111.67,
          111.67,
          "\u2026"
        ],
        "rul_point": [
          125.0,
          125.0,
          "\u2026"
        ],
        "rul_upper": [
          217.48,
          217.48,
          "\u2026"
        ]
      },
      "\u2026"
    ],
    "evaluated_once": true,
    "selected_by_true_rul_bin": [
      {
        "n": 19,
        "mae": 2.9347901623314137,
        "bias": 1.277044659905932,
        "rmse": 3.5022397721110576,
        "true_rul": "0-24"
      },
      {
        "n": 11,
        "mae": 2.618711428987178,
        "bias": -1.0574603510454814,
        "rmse": 3.748033138984478,
        "true_rul": "25-49"
      },
      "\u2026"
    ]
  },
  "permutation_importance": {
    "data": "20 calibration engines",
    "scoring": "RMSE increase when a feature is shuffled",
    "features": [
      {
        "std": 0.10598707770635152,
        "mean": 5.159482888142707,
        "feature": "sensor_11_delta"
      },
      {
        "std": 0.10578203739583796,
        "mean": 4.871533218482075,
        "feature": "cycle"
      },
      "\u2026"
    ]
  },
  "features": {
    "window": 10,
    "columns": [
      "cycle",
      "setting_1",
      "\u2026"
    ],
    "sensors": [
      "sensor_2",
      "sensor_3",
      "\u2026"
    ],
    "settings": [
      "setting_1",
      "setting_2"
    ],
    "drop_rule": "fewer than 3 distinct values in fit-unit rows",
    "baseline_cycles": 10,
    "dropped_channels": [
      "setting_3",
      "sensor_1",
      "\u2026"
    ]
  },
  "conformal": {
    "alpha": 0.1,
    "bin_edges": [
      67.18536038217884,
      120.62314779520553
    ],
    "bin_counts": [
      1284,
      1284,
      "\u2026"
    ],
    "lower_offsets": [
      7.252821621965317,
      23.782652720855438,
      "\u2026"
    ],
    "upper_offsets": [
      8.264138037186278,
      31.34124438651895,
      "\u2026"
    ]
  },
  "split": {
    "strategy": "by unit_id; seeded permutation",
    "fit_units": [
      1,
      2,
      "\u2026"
    ],
    "calibration_units": [
      3,
      5,
      "\u2026"
    ]
  }
}
```

## Error

`GET /api/v1/engines/ENG-999`

```json
{
  "error": {
    "code": "engine_not_found",
    "message": "No engine 'ENG-999'"
  }
}
```

## Maintenance and scenarios

Costs are fictional integer units. Times are UTC; `*_local` carry the facility's offset. See
[optimization.md](optimization.md) for the model.

| Method | Route | Notes |
|---|---|---|
| GET | `/api/v1/maintenance/resources` | Facilities, bays, rosters (local time), spare lots, job types |
| GET | `/api/v1/maintenance/plan` | Baseline plan of the seeded job cards; `?buffer=` re-derives cards |
| GET | `/api/v1/scenarios` | Recent scenarios with per-method status (`limit` ≤ 100) |
| POST | `/api/v1/scenarios` | Validate and store assumptions (201). Does not solve |
| POST | `/api/v1/scenarios/{id}/solve` | Queue baseline + CP-SAT (202); 409 `already_running` |
| GET | `/api/v1/scenarios/{id}` | Assumptions, status, both plans, comparison rows |

Assumptions: `buffer` (0–200), `threshold_policy` (`penalty` \| `hard`), `bay_changes`
({facility: delta}, result ≥ 0, delta ≤ +3), `part_delay_hours` (0–168, delays inbound lots),
`grounded_aircraft` (≤ 5), `added_jobs` (≤ 5, one job per ship), `time_limit_s` (0.5–30).
Error codes: `unknown_facility`, `invalid_bay_change`, `unknown_aircraft`, `duplicate_aircraft`,
`duplicate_job`, `validation_error`, `scenario_not_found`, `already_running`.

`pct_change` is `null` when the baseline value is 0 or either side has no plan.

`GET /api/v1/maintenance/resources` (first facility and two lots shown)

```json
{
  "horizon_start": "2027-03-11T10:00:00Z",
  "horizon_end": "2027-03-18T10:00:00Z",
  "facilities": [
    {
      "code": "ATL",
      "name": "ATL line",
      "kind": "line",
      "timezone": "America/New_York",
      "supports": [
        "borescope"
      ],
      "bays": [
        {
          "id": "ATL-1",
          "name": "1"
        }
      ],
      "shifts": [
        {
          "name": "day",
          "start_local": "06:00:00",
          "end_local": "22:00:00",
          "technicians": 3,
          "is_night": false
        },
        {
          "name": "night",
          "start_local": "22:00:00",
          "end_local": "06:00:00",
          "technicians": 2,
          "is_night": true
        }
      ]
    }
  ],
  "parts": [
    {
      "id": "SE-DEN",
      "part_type": "spare_engine",
      "location": "DEN",
      "quantity": 2,
      "available_at": "2027-03-11T10:00:00Z",
      "transfer_lead_hours": 18
    },
    {
      "id": "SE-DEN-INBOUND",
      "part_type": "spare_engine",
      "location": "DEN",
      "quantity": 1,
      "available_at": "2027-03-13T22:00:00Z",
      "transfer_lead_hours": 18
    }
  ],
  "job_types": [
    {
      "id": "engine_change",
      "label": "Engine change",
      "duration_hours": 12,
      "technicians": 4,
      "part_type": "spare_engine"
    },
    {
      "id": "borescope",
      "label": "Borescope inspection",
      "duration_hours": 4,
      "technicians": 2,
      "part_type": null
    }
  ]
}
```

`GET /api/v1/maintenance/plan` (one placement and job shown)

```json
{
  "method": "baseline",
  "status": "FEASIBLE",
  "objective": 3514,
  "best_bound": null,
  "wall_ms": 1,
  "costs": {
    "cancellations": 2300,
    "threshold": 150,
    "unscheduled": 0,
    "labor": 1064,
    "transfers": 0,
    "total": 3514
  },
  "metrics": {
    "jobs_total": 6,
    "jobs_scheduled": 6,
    "jobs_unscheduled": 0,
    "thresholds_missed": 1,
    "cycles_over_threshold": 1,
    "cancelled_legs": 23,
    "grounded_legs": 0,
    "labor_hours": 248,
    "part_transfers": 0,
    "bay_utilization": 0.0761904761904762
  },
  "placements": [
    {
      "job_id": "MX-ENG-801",
      "engine_id": "ENG-801",
      "aircraft_id": "801",
      "job_type": "engine_change",
      "reason": "critical",
      "facility": "ORD",
      "bay": "ORD-1",
      "start": "2027-03-11T10:00:00Z",
      "end": "2027-03-11T22:00:00Z",
      "start_local": "2027-03-11T04:00:00-06:00",
      "end_local": "2027-03-11T16:00:00-06:00",
      "tz_abbr": "CST",
      "cancelled_flights": [
        "NS1000-20270311",
        "NS1001-20270311",
        "NS1002-20270311",
        "NS1003-20270311"
      ],
      "cycles_over": 0,
      "part_lot": "SE-ORD",
      "part_from": "ORD",
      "labor_hours": 48,
      "why": [
        "Cancels 4 legs (NS1000 11 Mar 12:25Z to NS1003); ship returns to ORD 12 Mar 03:30Z",
        "Before threshold (NS1000 departs ORD 11 Mar 12:25Z)",
        "spare_engine from ORD stock"
      ]
    }
  ],
  "unscheduled": [],
  "explanations": [],
  "verified": true,
  "jobs": [
    {
      "id": "MX-ENG-801",
      "engine_id": "ENG-801",
      "aircraft_id": "801",
      "job_type": "engine_change",
      "reason": "critical",
      "duration_hours": 12,
      "technicians": 4,
      "part_type": "spare_engine",
      "due_flight_id": "NS1000-20270311",
      "due_at": "2027-03-11T12:25:00Z"
    }
  ]
}
```

`POST /api/v1/scenarios` → 201

```json
{
  "id": 12,
  "name": "DEN bay out",
  "status": "created",
  "assumptions": {
    "buffer": 10,
    "threshold_policy": "penalty",
    "bay_changes": {
      "DEN": -1
    },
    "part_delay_hours": 0,
    "grounded_aircraft": [],
    "added_jobs": [],
    "time_limit_s": 10.0
  }
}
```

`POST /api/v1/scenarios/{id}/solve` → 202

```json
{
  "id": 12,
  "status": "queued"
}
```

`GET /api/v1/scenarios/{id}` (placements and jobs elided; two comparison rows shown)

```json
{
  "id": 12,
  "name": "DEN bay out",
  "status": "solved",
  "error": null,
  "created_at": "2026-11-17T01:50:04.413900Z",
  "updated_at": "2026-11-17T01:50:04.696989Z",
  "assumptions": {
    "buffer": 10,
    "threshold_policy": "penalty",
    "bay_changes": {
      "DEN": -1
    },
    "part_delay_hours": 0,
    "grounded_aircraft": [],
    "added_jobs": [],
    "time_limit_s": 10.0
  },
  "baseline": {
    "method": "baseline",
    "status": "FEASIBLE",
    "objective": 3862,
    "best_bound": null,
    "wall_ms": 1,
    "costs": {
      "cancellations": 2300,
      "threshold": 450,
      "unscheduled": 0,
      "labor": 1112,
      "transfers": 0,
      "total": 3862
    },
    "metrics": {
      "jobs_total": 6,
      "jobs_scheduled": 6,
      "jobs_unscheduled": 0,
      "thresholds_missed": 2,
      "cycles_over_threshold": 3,
      "cancelled_legs": 23,
      "grounded_legs": 0,
      "labor_hours": 248,
      "part_transfers": 0,
      "bay_utilization": 0.09523809523809523
    },
    "verified": true,
    "placements": "\u2026",
    "unscheduled": [],
    "explanations": [],
    "jobs": "\u2026"
  },
  "optimized": {
    "method": "optimized",
    "status": "OPTIMAL",
    "objective": 3362,
    "best_bound": 3362.0,
    "wall_ms": 121,
    "costs": {
      "cancellations": 1600,
      "threshold": 750,
      "unscheduled": 0,
      "labor": 1012,
      "transfers": 0,
      "total": 3362
    },
    "metrics": {
      "jobs_total": 6,
      "jobs_scheduled": 6,
      "jobs_unscheduled": 0,
      "thresholds_missed": 2,
      "cycles_over_threshold": 5,
      "cancelled_legs": 16,
      "grounded_legs": 0,
      "labor_hours": 248,
      "part_transfers": 0,
      "bay_utilization": 0.09523809523809523
    },
    "verified": true,
    "placements": "\u2026",
    "unscheduled": [],
    "explanations": [],
    "jobs": "\u2026"
  },
  "comparison": [
    {
      "key": "cancelled_legs",
      "label": "Cancelled legs",
      "unit": "legs",
      "baseline": 23.0,
      "optimized": 16.0,
      "delta": -7.0,
      "pct_change": -0.30434782608695654,
      "better": "lower"
    },
    {
      "key": "total",
      "label": "Simulated cost",
      "unit": "units",
      "baseline": 3862.0,
      "optimized": 3362.0,
      "delta": -500.0,
      "pct_change": -0.1294665976178146,
      "better": "lower"
    }
  ]
}
```

Infeasible scenario: `optimized.explanations`

```json
[
  {
    "job_id": null,
    "code": "resource_conflict",
    "message": "Cannot all be on time: ENG-802 before NS1010 departs DEN 11 Mar 13:25Z; ENG-808 before NS1070 departs DEN 11 Mar 13:45Z. Shared: DEN (ENG-802, ENG-808): 1 bay, 4 to 8 technicians by shift | spare_engine: 2 at DEN from 11 Mar 10:00Z, 1 at DEN from 13 Mar 22:00Z, 2 at ORD from 11 Mar 10:00Z"
  }
]
```

Invalid assumptions → 422

```json
{
  "error": {
    "code": "unknown_facility",
    "message": "No maintenance facility 'XXX'"
  }
}
```
