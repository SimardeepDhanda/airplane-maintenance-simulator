# Progress

## Current phase

**Phase 0 – Research and scaffold: complete, awaiting approval.** Next: Phase 1 (real ML pipeline on FD001).

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
