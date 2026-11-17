# Deployment (free tiers)

Nothing here is deployed yet. This is the configuration and the steps to deploy it without paid
services. Each piece is configured only through environment variables.

| Piece | Host (free tier) | Config in repo |
|---|---|---|
| Postgres 16 | [Neon](https://neon.tech) | migrations in `services/api/migrations` |
| API (FastAPI + CP-SAT) | [Render](https://render.com) web service, Docker runtime | `render.yaml`, `services/api/Dockerfile` |
| Web (Next.js) | [Vercel](https://vercel.com) Hobby | `apps/web` (auto-detected) |

Why this split: Render's free Postgres expires after 30 days, Neon's does not. Vercel builds Next.js
natively. The API image needs no files at runtime besides the database. The NASA data, the trained
model and the seeded fleet all live in Postgres once seeding has run.

## 1. Database (Neon)

1. Create a project (Postgres 16) and copy the connection string.
2. Change the scheme for SQLAlchemy/psycopg 3:
   `postgresql://…` becomes `postgresql+psycopg://…`. Keep `?sslmode=require`.

## 2. Seed it from your machine

The hosted API never downloads data or trains models. Run the pipeline locally and point it at Neon.
Pass `DATABASE_URL` as a make argument: make variables override values loaded from `.env`, but
plain environment variables do not.

```bash
make setup
make data pipeline                                    # NASA C-MAPSS download + model (local files)
make migrate seed DATABASE_URL='postgresql+psycopg://USER:PASSWORD@HOST/DB?sslmode=require'
```

`seed` resets and reloads the demo fleet, so it is safe to re-run.

## 3. API (Render)

1. New → Blueprint → select this repository. Render reads `render.yaml`.
2. Set the two secret variables it asks for:
   - `DATABASE_URL`: the Neon URL from step 1.
   - `CORS_ORIGINS`: the Vercel URL, e.g. `https://aerofleet.vercel.app` (comma-separated if several).
3. Deploy. The container runs `alembic upgrade head` and then serves on Render's `$PORT`.
   `/health` returns 503 until the database is reachable.

Free-tier behaviour to expect:
- The service sleeps after about 15 minutes idle, and the first request after that takes roughly a
  minute to wake. The web app shows its loading state, then retries (5xx and network errors only).
- 512 MB RAM. Measured locally, the API process uses about 250 MB resident after serving every
  endpoint and a solve.
- Scenario solves run in-process as background tasks. CP-SAT uses a single worker and a time limit
  (10 s by default, 30 s maximum, set per scenario), so a solve cannot hold the instance for long.

## 4. Web (Vercel)

1. Import the repository and set **Root Directory** to `apps/web`. Vercel detects Next.js and pnpm.
2. Set `NEXT_PUBLIC_API_URL` to the Render URL (e.g. `https://aerofleet-api.onrender.com`).
   The browser reads it, and it is baked in at build time, so redeploy after changing it.
3. Deploy, then put the Vercel URL in the API's `CORS_ORIGINS`.

## Checks after deploying

```bash
curl https://<api>/health                       # {"status":"ok","database":"ok",…}
curl https://<api>/api/v1/fleet/summary          # 20 aircraft, model version
PLAYWRIGHT_BASE_URL=https://<web> NEXT_PUBLIC_API_URL=https://<api> pnpm --filter web e2e
```

## Self-hosting instead

`make up` builds and runs Postgres, the API and the web app with Docker Compose. CI runs the same
images as a smoke test on every push.
