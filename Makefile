# Run from the repository root. Values in .env are exported to every recipe.
-include .env
export

PY_SOURCES := services/api/app services/api/tests services/api/migrations ml/src ml/tests optimization scripts

.PHONY: help setup db db-stop migrate api web data pipeline reproduce test e2e lint format typecheck check up down

help:  ## List targets
	@grep -hE '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-10s %s\n", $$1, $$2}'

setup:  ## Install Python + Node dependencies and create .env
	@test -f .env || cp .env.example .env
	uv sync --frozen
	pnpm install --frozen-lockfile

db:  ## Start PostgreSQL (Docker)
	docker compose up -d --wait db

db-stop:  ## Stop PostgreSQL
	docker compose stop db

migrate:  ## Apply database migrations
	uv run alembic -c services/api/alembic.ini upgrade head

api:  ## Run the API with reload on :8000
	uv run uvicorn --factory app.main:create_app --reload --port 8000

web:  ## Run the web app in dev mode on :3000
	pnpm dev

data:  ## Download and verify NASA C-MAPSS into data/raw/cmapss
	uv run python scripts/download_data.py

pipeline:  ## Train, calibrate, evaluate and save the FD001 model (needs `make data`)
	uv run python scripts/run_pipeline.py

reproduce:  ## Re-run the pipeline and compare with the committed metrics
	uv run pytest -m dataset

test:  ## Python tests (needs TEST_DATABASE_URL for DB tests)
	uv run pytest -m "not network and not dataset"

e2e:  ## Build the web app and run Playwright (starts API + web)
	pnpm build
	pnpm e2e

lint:  ## Ruff + ESLint + format checks
	uv run ruff check .
	uv run ruff format --check .
	pnpm lint
	pnpm format:check

format:  ## Apply formatters
	uv run ruff check --fix .
	uv run ruff format .
	pnpm format

typecheck:  ## mypy (strict) + tsc (strict)
	uv run mypy $(PY_SOURCES)
	pnpm typecheck

check: lint typecheck test  ## Everything CI runs except E2E and Docker

up:  ## Build and run db + api + web in Docker
	docker compose --profile app up --build -d --wait

down:  ## Stop all containers
	docker compose --profile app down
