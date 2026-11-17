"""Planning flags: how scheduled flights consume an engine's predicted cycles.

For predicted RUL R, lower bound L and n forecast legs: modeled margin = R - n, conservative
margin = L - n. A flag compares the conservative margin with a user-set planning buffer.
This is a simulation alert under a hypothetical policy, not an inspection requirement.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

PlanningStatus = Literal["ok", "review", "critical"]


@dataclass(frozen=True)
class Leg:
    flight_id: str
    departure: datetime
    cycles: int


@dataclass(frozen=True)
class PlanningAssessment:
    forecast_legs: int
    forecast_cycles: int
    margin: float  # R - n
    conservative_margin: float  # L - n
    status: PlanningStatus
    buffer: int
    # First leg after which the conservative margin falls below the buffer (None if never).
    first_flagged_flight_id: str | None
    first_flagged_departure: datetime | None
    flagged_flight_ids: tuple[str, ...]


def classify(conservative_margin: float, buffer: int) -> PlanningStatus:
    """critical: forecast legs exceed the lower bound; review: within the buffer; ok otherwise."""
    if conservative_margin < 0:
        return "critical"
    if conservative_margin < buffer:
        return "review"
    return "ok"


def assess(
    rul_point: float, rul_lower: float, legs: Sequence[Leg], buffer: int
) -> PlanningAssessment:
    if buffer < 0:
        raise ValueError("buffer must be >= 0")
    ordered = sorted(legs, key=lambda leg: (leg.departure, leg.flight_id))
    used = 0
    flagged: list[Leg] = []
    for leg in ordered:
        used += leg.cycles
        if rul_lower - used < buffer:
            flagged.append(leg)
    total = used
    conservative = rul_lower - total
    return PlanningAssessment(
        forecast_legs=len(ordered),
        forecast_cycles=total,
        margin=rul_point - total,
        conservative_margin=conservative,
        status=classify(conservative, buffer),
        buffer=buffer,
        first_flagged_flight_id=flagged[0].flight_id if flagged else None,
        first_flagged_departure=flagged[0].departure if flagged else None,
        flagged_flight_ids=tuple(leg.flight_id for leg in flagged),
    )
