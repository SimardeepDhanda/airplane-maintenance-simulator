# Maintenance optimization

Schedules one maintenance job per flagged engine over the 7-day horizon, against a fixed flight
schedule and finite maintenance resources. Two planners use the same placement options and the same
cost function, so their results are directly comparable:

- **Baseline (EDD):** jobs by earliest planning due date (then id), each in its first feasible slot
  (earliest start, then facility code). Deterministic and transparent. Ignores cost.
- **Optimizer (OR-Tools CP-SAT):** chooses all placements jointly to minimise total simulated cost.

Code: `optimization/src/aerofleet_opt/` (pure Python, no database). The API builds a `Problem`
from the seeded data and scenario assumptions (`services/api/app/services/maintenance.py`).

## Jobs

Every engine whose planning status is not `ok` gets a job card (assumption O13):

| Status | Job | Duration | Technicians | Part |
|---|---|---|---|---|
| critical (L − n < 0) | Engine change | 12 h | 4 | spare engine |
| review (L − n < buffer) | Borescope inspection | 4 h | 2 | — |

A job's **planning threshold** is the engine's first flagged leg (the first leg after which
L − cycles flown < buffer). Flying that leg or later legs before the job starts counts as
**cycles past threshold**. This is a scenario policy, not a legal limit.

## Time and placement options

- Hourly slots from the simulation start (11 Mar 2027 10:00Z), 168 slots.
- An option is *(facility, start slot)*. The aircraft must be on the ground at that station when the
  job starts (after its last arrival, before its next departure).
- If the job runs past the next departure, the legs from that departure are **cancelled up to and
  including the first leg that returns the aircraft to the same station** and departs again after
  the job ends (or to the end of the horizon). The remaining schedule keeps location continuity; no
  ferry flights are invented. Flight reassignment to other aircraft is not modelled (spec §6: keep
  the schedule fixed and count conflicts as disruptions).

## Constraints

| Constraint | Baseline | CP-SAT |
|---|---|---|
| Aircraft at the facility at job start | option enumeration | same options |
| No flight overlaps maintenance; location continuity | cancellation block | same |
| Facility supports the job type | option enumeration | same |
| Bays per facility per hour ≤ bay count | capacity check | `AddCumulative` (demand 1) |
| Technicians per facility per hour ≤ roster | capacity check | `AddCumulative` with fixed blocking intervals for low-staff shifts |
| Spare engine available at the facility by start (lot ready time + transfer lead time) | lot search | boolean per (option, lot) |
| Each lot used at most its quantity | counter | linear ≤ quantity |
| Job inside the horizon | enumeration | same |
| Hard threshold policy: no cycles past threshold, every job placed | skip options | per-job assumption literal |

Every returned plan is re-checked by an independent checker (`evaluate.verify`) that rebuilds
the kept flights, aircraft location, bay/technician usage per hour and part usage. The API reports
`verified: true` only when it finds no violation; tests assert it on every fixture.

## Objective (fictional integer cost units)

| Term | Weight |
|---|---|
| Cancelled leg | 100 |
| Cycle flown past threshold | 150 |
| Job not placed | 2,000 (+ its cycles past threshold) |
| Technician-hour, day / night shift | 4 / 5 |
| Spare engine moved between stations | 50 |

All terms are integers, so the reported total equals the sum of its components exactly (tested).

## Status and determinism

- `OPTIMAL`: CP-SAT proved optimality. `FEASIBLE`: incumbent within the time limit, **not proven
  optimal**. `INFEASIBLE`: proven. `UNKNOWN`: no solution within the time limit.
- Baseline: `FEASIBLE`, or `NO_SOLUTION` when it cannot place a job on time under the hard policy
  (a heuristic failure does not prove infeasibility).
- CP-SAT runs single-threaded with a fixed seed, so the same scenario gives the same plan.
- Time limit is a scenario input (0.5–30 s, default 10 s).

## Explanations

- **Before solving** (`diagnose`): a job with no compatible facility on the aircraft's route, no
  spare that can reach a usable slot, no slot with a bay and enough technicians, or (hard policy) no
  slot that starts before its threshold.
- **Infeasible:** each job gets an assumption literal ("on time"). CP-SAT returns a sufficient
  subset; a deletion filter re-solves without each member to reduce it to an irreducible conflict.
  The message names those jobs, their thresholds, and the bays, rosters and spare-engine lots they
  share.
- **Per placement:** ground time used or legs cancelled, threshold status, spare source, and what
  blocks the earliest alternative given the rest of the plan (bays in use by named jobs, technicians
  on shift, part not yet available) or which cost terms make it more expensive.

## Measured outcomes (seeded NASA fleet, model fd001-hgb-3a2ffab7)

Run with `uv run python` against `make seed` data; costs are fictional units.

| Scenario | Jobs | Baseline | Optimized | Cost B → O | Cancelled legs B → O | Cycles past threshold B → O | Optimizer ms |
|---|---|---|---|---|---|---|---|
| Default week | 6 | FEASIBLE | OPTIMAL | 3,514 → 3,102 (−12%) | 23 → 19 | 1 → 1 | 104 |
| Inbound spare +24 h | 6 | FEASIBLE | OPTIMAL | 4,214 → 3,802 (−10%) | 24 → 20 | 5 → 5 | 139 |
| DEN bay out | 6 | FEASIBLE | OPTIMAL | 3,862 → 3,362 (−13%) | 23 → 16 | 3 → 5 | 95 |
| Buffer 40 | 10 | FEASIBLE | OPTIMAL | 8,796 → 5,310 (−40%) | 52 → 20 | 16 → 14 | 160 |
| Hard threshold | 6 | NO_SOLUTION | INFEASIBLE | — | — | — | 218 |
| Hard threshold, DEN bay out | 6 | NO_SOLUTION | INFEASIBLE | — | — | — | 282 |

"DEN bay out" shows a real trade-off: the optimizer accepts 2 more cycles past threshold to cancel
7 fewer legs, because that is cheaper under the stated weights. Different weights give different
plans; they are inputs, not facts.

Infeasible explanations from the last two rows:

- *Hard threshold:* five engine changes (ENG-801, 802, 804, 808, 812) compete for five spare
  engines, one of which arrives at DEN on 13 Mar 22:00Z, too late for ENG-804's threshold.
- *Hard threshold, DEN bay out:* "Cannot all be on time: ENG-802 before NS1010 departs DEN 11 Mar
  13:25Z; ENG-808 before NS1070 departs DEN 11 Mar 13:45Z. Shared: DEN (ENG-802, ENG-808): 1 bay…"
  Each job is feasible alone; both need the single DEN bay in the same morning. This is the
  deliberately infeasible demo preset.

## Tests

`optimization/tests/test_optimizer.py` (66 cases): bay and technician capacity, rosters, part lead
time and quantity, transfers, facility compatibility, cancellation continuity, the infeasible
fixture (each job feasible alone, core names both), penalty vs hard policy, objective = sum of
components, determinism, time-limit reporting, guarded percent change, and 50 randomised instances
where both planners must pass the independent checker and CP-SAT (when OPTIMAL) is never worse than
the baseline. API tests (`services/api/tests/test_api_maintenance.py`) re-check plans against the
flight schedule through the public endpoints.

## Limitations

- One job per aircraft; no flight reassignment, swaps or ferry flights.
- Hourly slots; job durations are fixed; technicians are interchangeable within a facility.
- Penalty weights are illustrative. The comparison is valid under those weights only.
- Solving runs in the API process (background task). Fine for this fleet size; a job queue would be
  needed for concurrent heavy use.
