# ADR 0001: Stack and repository layout

- **Status:** accepted (Phase 0)
- **Date:** 2026-11-17

## Context

The spec (§2) prescribes Next.js + FastAPI + PostgreSQL, Python ML with scikit-learn, and OR-Tools
CP-SAT. It suggests separate `ml/` and `optimization/` folders but allows folding them into the API
if packaging causes friction.

## Decision

1. **One uv workspace** (`pyproject.toml` at the root) with three members: `services/api`
   (`app`), `ml` (`aerofleet_ml`), `optimization` (`aerofleet_opt`). One lockfile (`uv.lock`), one venv.
   The API depends on the two libraries; they never depend on the API.
2. **pnpm workspace** for the frontend (`apps/web`), with a root `package.json` that proxies scripts.
3. **Python 3.12** pinned (`.python-version`, Docker, CI). Node 22.
4. **Tooling:** Ruff (lint and format), mypy `--strict`, pytest; ESLint (next core-web-vitals and
   typescript configs), Prettier, `tsc` with `strict`, `noUncheckedIndexedAccess` and
   `exactOptionalPropertyTypes`; Playwright.
5. **Single root `.env`** read by the API (pydantic-settings) and the web app (`next.config.ts` loads it).
6. **Self-hosted fonts** via `@fontsource` (IBM Plex) so builds do not depend on Google Fonts.
7. **Progress tracking:** `PROGRESS.md` only. The spec's `IMPLEMENTATION_STATUS.md` is folded into
   it to avoid two documents drifting.
8. **No Redis/Celery or background workers** until measured latency requires them.
9. **Direct pushes to `main`** at the owner's request; CI runs on every push.

## Consequences

- Cross-package imports are type-checked together (`mypy` over all packages).
- The API image is built from the repo root so it can install the workspace libraries.
- Adding heavy ML/solver dependencies (scikit-learn, OR-Tools) affects only the packages that
  declare them, deferred to Phases 1 and 4.
