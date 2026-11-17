# ADR 0003: Maintenance scheduling model

- **Status:** accepted (Phase 4)
- **Date:** 2026-11-17

## Decision

- Hourly time slots over the 7-day horizon; one optional fixed-size interval per (job, facility,
  start) in CP-SAT, with cumulative constraints for bays and technicians.
- The flight schedule stays fixed. A job that overruns ground time cancels the aircraft's legs until
  it is back at the same station after the job ends. This keeps location continuity without
  modelling reassignment.
- The baseline and CP-SAT share option enumeration and scoring; a separate checker verifies every
  plan.
- Threshold policy is a scenario input: penalty (cost per cycle past threshold) or hard (assumption
  literals, which also yield infeasibility cores).
- Solves run as a FastAPI background task; clients poll `GET /scenarios/{id}`.

## Alternatives considered

- **Continuous-time CP-SAT intervals with presence derived from flights.** More exact but needs
  location tracking inside the model; option enumeration gives the same answers at hourly
  resolution and keeps the checker simple.
- **Flight reassignment (aircraft swaps).** Higher realism, much larger model; deferred per spec §6.
- **MILP (CBC/HiGHS).** Viable, but CP-SAT's cumulative and assumption support fit the resource
  and explanation needs directly.
- **Celery/RQ job queue.** Adds infrastructure for solves that take well under a second here.

## Consequences

- Placement explanations are exact for the modelled constraints.
- Plans can only cancel whole round trips back to the job's station, which over-states disruption
  compared with an airline that would swap aircraft.
