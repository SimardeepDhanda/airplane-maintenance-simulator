# Progress

## Current phase

**Phase 1 – Real ML pipeline: complete, awaiting approval.** Next: Phase 2 (fictional airline and fleet API).

## Phase 1 – Real ML pipeline (FD001)

### Completed

- Loading with RUL targets: train `max_cycle − cycle`; test `RUL file + offset`, mapped line i → unit i.
- Engine-level split (80 fit / 20 calibration, seeded); channel selection on fit engines only.
- Causal features: value, 10-cycle rolling mean/std, drift from the engine's early-life level.
- Baselines (constant, linear on cycle, Ridge) and HistGradientBoosting, each with capped (125) and
  uncapped targets; grouped 5-fold CV selection; single final evaluation on the official test split.
- Metrics: RMSE, MAE, bias, PHM08 score (published definition), per true-RUL bin, all-cycle variant.
- Split-conformal intervals (two tails, per predicted-RUL tertile) with measured coverage and width.
- Permutation importance on calibration engines.
- `RulPredictor.predict(history) -> {rul_point, rul_lower, rul_upper, model_version,
  observed_through_cycle}` and `predict_trajectory`; input validation.
- One command (`make pipeline`) writes `model.joblib` + `manifest.json` + `metrics.json`; `LATEST` pointer.
- Explicitly synthetic C-MAPSS-format fixture for tests/CI (`data_kind: synthetic_fixture`).
- Docs: model card, data dictionary, assumptions M1–M5, ADR 0002, README results.

### Measured results (official test, last cycle, 100 engines)

Selected HistGradientBoosting (capped): RMSE 11.44, MAE 8.35, PHM08 200. Ridge baseline: RMSE 16.89.
Intervals (nominal 90%): 90.0% coverage, 43.9 mean width; all-cycle coverage 77.5% (lower bound 96.2%).
Full tables in `docs/model_card.md`.

### Files and modules

`ml/src/aerofleet_ml/{data/load.py, data/synthetic.py, features/build.py, train/{split,models}.py,
evaluate/{metrics,conformal}.py, inference/predictor.py, pipeline.py}`, `scripts/run_pipeline.py`,
`ml/tests/{conftest,test_load,test_features,test_split,test_metrics,test_conformal,test_pipeline,
test_reproducibility}.py`, `ml/artifacts/fd001-hgb-3a2ffab7/{manifest,metrics}.json`, `ml/artifacts/LATEST`.

### Verification (2026-11-17)

| Check | Result |
|---|---|
| `make check` (ruff, format, eslint, prettier, mypy strict, tsc, pytest) | 55 passed (network + dataset deselected) |
| `make pipeline` twice | identical metrics (excluding timestamp) and version id |
| Independent recomputation of test RMSE/MAE from `RUL_FD001.txt` | matches (11.437 / 8.345) |
| `pytest -m dataset` (re-train, compare with committed metrics) | passed |

Tests cover target derivation, RUL-file mapping, split integrity and seeding, no future rows in features
(truncation test), no cross-engine mixing, window alignment, channel selection on given rows only,
PHM08 known values, conformal coverage on exchangeable data, interval ordering/non-negativity, bin
adaptivity, pipeline determinism, every candidate evaluated, selection by CV only, predictor
round-trip, trajectory = truncated-history prediction, invalid-input rejection.

### Known limitations

- FD001 only. Predictions saturate at 125 cycles. 20 calibration engines → noisy interval offsets.
- Coverage is not guaranteed (temporal dependence); upper bound under-covers early-life cycles.
- No LSTM/GRU (optional; not earned).
- The model is not yet served by the API (Phase 2 endpoints).

## Phase 0 – Research and scaffold

### Completed

- Monorepo: uv workspace (`services/api`, `ml`, `optimization`) + pnpm workspace (`apps/web`), one lockfile each.
- API: env-validated settings, SQLAlchemy engine, `GET /health` (200 ok / 503 degraded, same schema), CORS, app factory.
- Alembic configured; baseline revision `0001` (no tables yet).
- NASA C-MAPSS acquisition: `scripts/download_data.py` → `aerofleet_ml.data.cmapss` (checksum-verified,
  nested-zip aware, atomic extract, `SOURCE.json` provenance, FD001 structural validation).
- Web shell: design tokens, status rail (Simulation label, API/DB status, UTC clock), grouped nav that
  collapses on mobile, one route per section with an explicit "Not built yet · Phase N" state, 404 page.
- Docker: API and web images, Compose (db always; api + web under the `app` profile), test DB init.
- CI: Python checks + tests with Postgres, web checks + build, Playwright against live API + Postgres,
  Docker Compose smoke test, weekly real-dataset check.
- Docs: README, architecture (Mermaid), assumptions, data provenance, ADR 0001.

### Files and modules

`pyproject.toml`, `package.json`, `pnpm-workspace.yaml`, `Makefile`, `.env.example`, `docker-compose.yml`,
`services/api/{app,migrations,tests,Dockerfile,alembic.ini}`, `ml/src/aerofleet_ml/data/cmapss.py`,
`ml/tests/test_cmapss.py`, `optimization/src/aerofleet_opt`, `scripts/download_data.py`,
`apps/web/{app,components,lib,e2e,Dockerfile}`, `.github/workflows/ci.yml`, `docs/`.

### Verification (run 2026-11-17 in a fresh clone of the commit)

| Check | Result |
|---|---|
| `make setup` → `make migrate` | OK |
| `make check` (ruff, ruff format, eslint, prettier, mypy strict, tsc strict, pytest) | 18 passed, 1 network test deselected |
| `pytest -m network` (real NASA download) | passed; FD001 20,631 / 13,096 rows, 100 / 100 units, 100 RUL rows |
| `make data` | archive checksum matched; 13 files written |
| `make e2e` (Playwright, desktop + mobile) | 16 passed |
| Standalone web build (`NEXT_OUTPUT=standalone`) served by `node server.js` | page + CSS 200 |
| Docker Compose / image builds | **not run locally** (no Docker daemon in the dev container); verified by the CI `docker` job |

Tests cover: health ok / DB down / OpenAPI contract, settings validation, migration up/down round trip,
dataset checksum rejection, missing files, path-traversal entries, failed-rerun safety, column-count and
RUL/unit mismatch errors; UI routing, active nav state, API online / unreachable / DB degraded states,
404 recovery, keyboard focus, no horizontal overflow.

### Decisions

See `docs/decisions/0001-stack-and-layout.md`. Notably: uv workspace instead of separate services;
single root `.env`; `PROGRESS.md` replaces `IMPLEMENTATION_STATUS.md`; IBM Plex self-hosted.

### Known limitations

- `nasa.gov` / `data.nasa.gov` were unreachable from the dev container; the NASA-linked S3 URL works.
  No explicit licence is stated on the NASA repository page (see `docs/data_provenance.md`).
- No domain tables, models or endpoints beyond `/health` yet, by design.

## Remaining phases

1. Real ML pipeline (FD001 parsing, group split, baselines, improved model, conformal intervals, manifest, model card, inference).
2. Fictional airline simulation + fleet API.
3. Frontend core.
4. Maintenance planner (heuristic + CP-SAT).
5. Polish and deploy.
