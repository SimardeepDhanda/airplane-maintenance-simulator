# Performance

Measured on the seeded real-data demo (20 aircraft, 555 legs, 6 maintenance jobs), API and
Postgres on the same machine, production web build (`next start`). Times are server round trips
from `curl`, 15 warm requests each.

## API

| Endpoint | p50 | p95 | Body (uncompressed) |
|---|---|---|---|
| `GET /fleet/summary` | 12 ms | 15 ms | 0.3 KB |
| `GET /engines` | 13 ms | 17 ms | 8 KB |
| `GET /engines/ENG-802` | 12 ms | 15 ms | 14 KB |
| `GET /engines/ENG-802/history` | 10 ms | 12 ms | 33 KB |
| `GET /flights?page_size=1000` | 20 ms | 32 ms | 274 KB (17 KB gzipped) |
| `GET /models/metrics` | 4 ms | 5 ms | 40 KB |
| `GET /maintenance/resources` | 13 ms | 15 ms | 2 KB |
| `GET /maintenance/plan` | 21 ms | 27 ms | 6 KB |
| `GET /maintenance/plan?buffer=40` | 22 ms | 24 ms | 10 KB |

Scenario solves (baseline + CP-SAT + verification) are in [optimization.md](optimization.md); the
default week is proven optimal in about 0.1 s. Responses over 1 KB are gzipped
(`GZipMiddleware`). The API process holds about 250 MB resident after serving every endpoint and a
solve, which fits a 512 MB free instance.

## Web

Initial JavaScript per route, gzipped, from the script tags in the server-rendered HTML:

| Route | JS |
|---|---|
| `/overview`, `/flights`, `/maintenance`, `/scenarios` | 223–224 KB |
| `/engines` | 235 KB |
| `/engines/[id]`, `/methodology` | 340–347 KB |

About 220 KB is shared: React DOM (72 KB), zod (39 KB), TanStack Query/Table and the app shell.
Recharts (119 KB) loads only on the two pages with Recharts charts; the rotation timeline and the
maintenance calendar are plain DOM. Largest Contentful Paint on a cold load was 50–450 ms locally.

Not done, and why: swapping zod for `zod/mini` or Recharts for hand-written SVG would save roughly
150 KB on the heaviest pages. That is not worth the churn at this size.
