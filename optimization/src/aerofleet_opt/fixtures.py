"""Small hand-checkable problems for tests and documentation.

Stations: HUB has a maintenance facility; OUT is a line station with no facility. Times are UTC
from 2027-03-11 10:00. Every aircraft flies HUB -> OUT -> HUB pairs.
"""

from __future__ import annotations

import random
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from aerofleet_opt.problem import (
    Aircraft,
    Facility,
    Job,
    Leg,
    PartLot,
    Problem,
    ThresholdPolicy,
)

START = datetime(2027, 3, 11, 10, tzinfo=UTC)
ENGINE_CHANGE = "engine_change"
BORESCOPE = "borescope"
SPARE = "spare_engine"


def leg(ac: str, n: int, origin: str, dest: str, dep_h: float, block_h: float = 2.0) -> Leg:
    dep = START + timedelta(hours=dep_h)
    return Leg(f"{ac}-{n}", f"T{n:03d}", origin, dest, dep, dep + timedelta(hours=block_h))


def rotation(ac: str, departures: list[float], home: str = "HUB", away: str = "OUT") -> Aircraft:
    legs = []
    station = home
    for n, dep in enumerate(departures):
        dest = away if station == home else home
        legs.append(leg(ac, n, station, dest, dep))
        station = dest
    return Aircraft(ac, home, tuple(legs))


def facility(
    code: str = "HUB",
    bays: int = 1,
    day: int = 8,
    night: int = 4,
    horizon: int = 48,
    supports: frozenset[str] = frozenset({ENGINE_CHANGE, BORESCOPE}),
) -> Facility:
    # Day shift 06:00-18:00 UTC for simplicity in fixtures.
    is_night = tuple(not 6 <= (START + timedelta(hours=s)).hour < 18 for s in range(horizon))
    roster = tuple(night if n else day for n in is_night)
    return Facility(code, f"{code} base", bays, supports, roster, is_night)


def engine_change(job_id: str, ac: str, threshold_leg: int | None, hours: int = 8) -> Job:
    return Job(job_id, ac, f"ENG-{ac}", ENGINE_CHANGE, hours, 4, SPARE, threshold_leg, "critical")


def borescope(job_id: str, ac: str, threshold_leg: int | None) -> Job:
    return Job(job_id, ac, f"ENG-{ac}", BORESCOPE, 4, 2, None, threshold_leg, "review")


def feasible(policy: ThresholdPolicy = "penalty") -> Problem:
    """Two ships, one bay, two spares: both jobs fit before their thresholds if sequenced."""
    a = rotation("A1", [12, 16, 36, 40])  # on ground at HUB 10:00-22:00Z, then 04:00Z-
    b = rotation("B1", [14, 18, 38, 42])
    return Problem(
        start=START,
        horizon_slots=48,
        aircraft=(a, b),
        facilities=(facility(bays=1, day=8, night=4),),
        lots=(PartLot("L1", SPARE, "HUB", 2, 0, 12),),
        jobs=(engine_change("J-A1", "A1", 2), borescope("J-B1", "B1", 2)),
        threshold_policy=policy,
    )


def infeasible_hard() -> Problem:
    """Deliberately infeasible under the hard policy.

    Two ships each need an 8 h engine change that must start before their first departure
    (16:00Z and 16:30Z, i.e. within 6 h of the 10:00Z start) at a single-bay facility. Either job
    alone fits (cancelling legs if needed); both cannot share the bay.
    """
    a = rotation("A1", [6, 10, 30, 34])
    b = rotation("B1", [6.5, 10.5, 30.5, 34.5])
    return Problem(
        start=START,
        horizon_slots=48,
        aircraft=(a, b),
        facilities=(facility(bays=1, day=8, night=8),),
        lots=(PartLot("L1", SPARE, "HUB", 2, 0, 12),),
        jobs=(engine_change("J-A1", "A1", 0), engine_change("J-B1", "B1", 0)),
        threshold_policy="hard",
    )


def no_facility() -> Problem:
    """The only facility cannot do engine changes."""
    p = feasible()
    fac = replace(p.facilities[0], supports=frozenset({BORESCOPE}))
    return replace(p, facilities=(fac,))


def random_problem(seed: int, policy: ThresholdPolicy = "penalty") -> Problem:
    """Randomised small instance for property tests (2 facilities, 3-5 ships)."""
    rng = random.Random(seed)
    horizon = 48
    aircraft = []
    jobs = []
    for i in range(rng.randint(3, 5)):
        home = rng.choice(["HUB", "MRO"])
        t = rng.uniform(0, 6)
        deps = []
        while t < horizon - 3:
            deps.append(round(t, 2))
            t += rng.uniform(3, 9)
        ac = rotation(f"S{i}", deps, home=home, away="OUT")
        aircraft.append(ac)
        threshold = rng.choice([None, 0, 1, 2, 3])
        if threshold is not None and threshold >= len(ac.legs):
            threshold = None
        if rng.random() < 0.6:
            jobs.append(engine_change(f"J{i}", ac.id, threshold, hours=rng.choice([6, 8, 10])))
        else:
            jobs.append(borescope(f"J{i}", ac.id, threshold))
    facilities = (
        facility("HUB", bays=rng.randint(1, 2), day=8, night=rng.choice([2, 4]), horizon=horizon),
        facility(
            "MRO",
            bays=1,
            day=6,
            night=rng.choice([0, 4]),
            horizon=horizon,
            supports=frozenset({BORESCOPE, ENGINE_CHANGE} if rng.random() < 0.5 else {BORESCOPE}),
        ),
    )
    lots = (
        PartLot("H", SPARE, "HUB", rng.randint(0, 2), rng.randint(0, 12), 10),
        PartLot("M", SPARE, "MRO", rng.randint(0, 2), rng.randint(0, 24), 10),
    )
    return Problem(
        START, horizon, tuple(aircraft), facilities, lots, tuple(jobs), threshold_policy=policy
    )
