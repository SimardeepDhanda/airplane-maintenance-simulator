"""Fictional maintenance resources for Northstar Air (illustrative values, not industry data).

Two hangars at the hubs handle engine changes and borescope inspections; a line station at ATL can
only do borescope inspections. Technician rosters are daily shifts in local time. Spare engines are
held at the hubs, with one more inbound to DEN.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

ENGINE_CHANGE = "engine_change"
BORESCOPE = "borescope"
SPARE_ENGINE = "spare_engine"


@dataclass(frozen=True)
class JobTypeSpec:
    label: str
    duration_hours: int
    technicians: int
    part_type: str | None


JOB_TYPES: dict[str, JobTypeSpec] = {
    ENGINE_CHANGE: JobTypeSpec("Engine change", 12, 4, SPARE_ENGINE),
    BORESCOPE: JobTypeSpec("Borescope inspection", 4, 2, None),
}
# Planning status -> job card raised for it (scenario policy, documented in assumptions.md).
JOB_FOR_STATUS: dict[str, str] = {"critical": ENGINE_CHANGE, "review": BORESCOPE}


@dataclass(frozen=True)
class ShiftSpec:
    name: str
    start: time
    end: time  # end < start wraps past midnight
    technicians: int
    is_night: bool


@dataclass(frozen=True)
class FacilitySpec:
    code: str
    name: str
    kind: str
    bays: int
    supports: tuple[str, ...]
    shifts: tuple[ShiftSpec, ...]


_HANGAR_SHIFTS = (
    ShiftSpec("day", time(6), time(18), 8, False),
    ShiftSpec("night", time(18), time(6), 4, True),
)

FACILITIES: tuple[FacilitySpec, ...] = (
    FacilitySpec("ORD", "ORD hangar", "hangar", 2, (ENGINE_CHANGE, BORESCOPE), _HANGAR_SHIFTS),
    FacilitySpec("DEN", "DEN hangar", "hangar", 2, (ENGINE_CHANGE, BORESCOPE), _HANGAR_SHIFTS),
    FacilitySpec(
        "ATL",
        "ATL line",
        "line",
        1,
        (BORESCOPE,),
        (
            ShiftSpec("day", time(6), time(22), 3, False),
            ShiftSpec("night", time(22), time(6), 2, True),
        ),
    ),
)


@dataclass(frozen=True)
class PartSpec:
    id: str
    part_type: str
    location: str
    quantity: int
    available_after: timedelta  # from simulation start
    transfer_lead_hours: int


PARTS: tuple[PartSpec, ...] = (
    PartSpec("SE-ORD", SPARE_ENGINE, "ORD", 2, timedelta(0), 18),
    PartSpec("SE-DEN", SPARE_ENGINE, "DEN", 2, timedelta(0), 18),
    PartSpec("SE-DEN-INBOUND", SPARE_ENGINE, "DEN", 1, timedelta(hours=60), 18),
)


def shift_at(shifts: tuple[ShiftSpec, ...], local: time) -> ShiftSpec | None:
    for s in shifts:
        inside = s.start <= local < s.end if s.start < s.end else local >= s.start or local < s.end
        if inside:
            return s
    return None


def roster(
    shifts: tuple[ShiftSpec, ...], timezone: str, start: datetime, slots: int
) -> tuple[tuple[int, ...], tuple[bool, ...]]:
    """Technicians on shift and night flag for each hourly slot, evaluated in local time."""
    tz = ZoneInfo(timezone)
    techs: list[int] = []
    night: list[bool] = []
    for s in range(slots):
        local = (start + timedelta(hours=s)).astimezone(tz).time()
        shift = shift_at(shifts, local)
        techs.append(shift.technicians if shift else 0)
        night.append(shift.is_night if shift else True)
    return tuple(techs), tuple(night)
