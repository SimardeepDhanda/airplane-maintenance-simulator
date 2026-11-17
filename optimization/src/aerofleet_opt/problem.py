"""Problem definition for the maintenance scheduler.

Time is discretised into hourly slots from `Problem.start`. Slot `s` covers [start + s h, start +
(s + 1) h). The flight schedule is fixed: a maintenance job either fits in a ground window or
cancels a contiguous block of the aircraft's legs that returns it to the same station, so location
continuity of the remaining schedule always holds (no ferry flights are invented).

All costs are fictional integer weights (see `Weights`); objective components are integers, so the
reported total is the exact sum of its parts.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Literal

SLOT = timedelta(hours=1)
ThresholdPolicy = Literal["penalty", "hard"]


@dataclass(frozen=True)
class Leg:
    id: str
    flight_number: str
    origin: str
    destination: str
    departure: datetime
    arrival: datetime
    cycles: int = 1


@dataclass(frozen=True)
class Aircraft:
    id: str
    initial_station: str
    legs: tuple[Leg, ...]  # chronological
    grounded: bool = False  # scenario: aircraft out of service; all its legs are cancelled


@dataclass(frozen=True)
class Facility:
    code: str  # airport code; one facility per station
    name: str
    bays: int
    supports: frozenset[str]
    technicians: tuple[int, ...]  # available technicians per slot (shift roster, local time)
    night: tuple[bool, ...]  # slot falls in a night shift (labour premium)


@dataclass(frozen=True)
class PartLot:
    id: str
    part_type: str
    location: str
    quantity: int
    ready_slot: int  # first slot the lot is usable at its own location
    transfer_slots: int  # extra slots to move a unit to another facility


@dataclass(frozen=True)
class Job:
    id: str
    aircraft_id: str
    engine_id: str | None
    job_type: str
    duration_slots: int
    technicians: int
    part_type: str | None
    # Index into the aircraft's legs of the first leg that would breach the planning threshold.
    # Flying legs[threshold_leg:] before maintenance counts as cycles over threshold.
    # None: no threshold applies.
    threshold_leg: int | None
    reason: str  # "critical" | "review" | "added"


@dataclass(frozen=True)
class Weights:
    """Fictional cost units. Integers so objective components sum exactly."""

    cancelled_leg: int = 100
    cycle_over_threshold: int = 150
    unscheduled_job: int = 2000
    tech_hour_day: int = 4
    tech_hour_night: int = 5
    part_transfer: int = 50


@dataclass(frozen=True)
class Problem:
    start: datetime
    horizon_slots: int
    aircraft: tuple[Aircraft, ...]
    facilities: tuple[Facility, ...]
    lots: tuple[PartLot, ...]
    jobs: tuple[Job, ...]
    weights: Weights = field(default_factory=Weights)
    threshold_policy: ThresholdPolicy = "penalty"

    def __post_init__(self) -> None:
        if self.start.tzinfo is None:
            raise ValueError("Problem.start must be timezone-aware")
        if self.horizon_slots <= 0:
            raise ValueError("horizon_slots must be positive")
        for f in self.facilities:
            if len(f.technicians) != self.horizon_slots or len(f.night) != self.horizon_slots:
                raise ValueError(f"facility {f.code}: roster length must equal horizon_slots")
            if f.bays < 0:
                raise ValueError(f"facility {f.code}: bays must be >= 0")
        ids = [a.id for a in self.aircraft]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate aircraft id")
        job_ids = [j.id for j in self.jobs]
        if len(job_ids) != len(set(job_ids)):
            raise ValueError("duplicate job id")
        per_aircraft = [j.aircraft_id for j in self.jobs]
        if len(per_aircraft) != len(set(per_aircraft)):
            raise ValueError("at most one maintenance job per aircraft")
        known = set(ids)
        for j in self.jobs:
            if j.aircraft_id not in known:
                raise ValueError(f"job {j.id}: unknown aircraft {j.aircraft_id}")
            if j.duration_slots <= 0 or j.technicians <= 0:
                raise ValueError(f"job {j.id}: duration and technicians must be positive")

    def hours(self, when: datetime) -> float:
        return (when - self.start) / SLOT

    def time_of(self, slot: int) -> datetime:
        return self.start + slot * SLOT

    def ceil_slot(self, when: datetime) -> int:
        return max(0, math.ceil(self.hours(when) - 1e-9))

    @property
    def end(self) -> datetime:
        return self.time_of(self.horizon_slots)

    def aircraft_by_id(self) -> dict[str, Aircraft]:
        return {a.id: a for a in self.aircraft}

    def facility_by_code(self) -> dict[str, Facility]:
        return {f.code: f for f in self.facilities}

    def flown_legs(self, aircraft: Aircraft) -> tuple[Leg, ...]:
        """Legs the scenario keeps before maintenance decisions (none if grounded)."""
        return () if aircraft.grounded else aircraft.legs
