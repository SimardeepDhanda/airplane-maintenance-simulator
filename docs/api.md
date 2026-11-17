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

Filters: `aircraft_id`, `engine_id`, `origin`, `destination`, `departure_from`/`departure_to` (UTC with offset), `flagged`. Local times carry the airport's offset and abbreviation.

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
