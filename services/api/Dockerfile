# Build context: repository root (the API imports workspace packages ml/ and optimization/).
FROM python:3.12-slim AS runtime

COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/opt/venv PATH=/opt/venv/bin:$PATH

WORKDIR /srv
COPY pyproject.toml uv.lock ./
COPY services/api/pyproject.toml services/api/
COPY ml/pyproject.toml ml/
COPY optimization/pyproject.toml optimization/
RUN mkdir -p services/api/app ml/src/aerofleet_ml optimization/src/aerofleet_opt \
 && uv sync --frozen --no-dev --no-install-workspace

COPY services/api services/api
COPY ml ml
COPY optimization optimization
RUN uv sync --frozen --no-dev

RUN useradd --system --uid 10001 app
USER app
EXPOSE 8000
# Hosts such as Render inject PORT; locally and in Compose it defaults to 8000.
CMD ["sh", "-c", "alembic -c services/api/alembic.ini upgrade head && exec uvicorn --factory app.main:create_app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
