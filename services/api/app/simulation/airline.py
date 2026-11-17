"""Deterministic generator for the fictional Northstar Air schedule.

Pure functions, no database. Times are UTC internally; local operating hours are evaluated in each
airport's IANA timezone, so daylight-saving changes are handled by zoneinfo.

Simplifications (documented in docs/assumptions.md):
- hub-and-spoke: from a hub any other station; from a non-hub station back to a hub;
- block time = 35 min + great-circle distance at 450 mph, rounded up to 5 minutes;
- minimum turn 45 min plus 0-60 min of seeded slack; departures between 06:00 and 21:30 local;
  aircraft overnight wherever their last leg ends;
- every leg consumes exactly one engine cycle.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

GENERATOR_VERSION = "airline-v1"
FLEET_TYPE = "Narrowbody (generic)"


@dataclass(frozen=True)
class AirportSpec:
    code: str
    name: str
    city: str
    timezone: str
    latitude: float
    longitude: float
    is_hub: bool = False
    has_maintenance_base: bool = False


# Real airport codes and locations; no real airline data, routes or branding.
AIRPORTS: tuple[AirportSpec, ...] = (
    AirportSpec(
        "ORD",
        "Chicago O'Hare International",
        "Chicago",
        "America/Chicago",
        41.9786,
        -87.9048,
        True,
        True,
    ),
    AirportSpec(
        "DEN", "Denver International", "Denver", "America/Denver", 39.8617, -104.6731, True, True
    ),
    AirportSpec(
        "ATL",
        "Hartsfield-Jackson Atlanta International",
        "Atlanta",
        "America/New_York",
        33.6367,
        -84.4281,
    ),
    AirportSpec(
        "BOS", "Boston Logan International", "Boston", "America/New_York", 42.3643, -71.0052
    ),
    AirportSpec(
        "PHX", "Phoenix Sky Harbor International", "Phoenix", "America/Phoenix", 33.4343, -112.0116
    ),
    AirportSpec(
        "SEA", "Seattle-Tacoma International", "Seattle", "America/Los_Angeles", 47.4490, -122.3093
    ),
)


@dataclass(frozen=True)
class ScheduleConfig:
    seed: int = 2027
    # 10:00 UTC = before 06:00 local at every station. The week spans the US DST change (Mar 14).
    start: datetime = datetime(2027, 3, 11, 10, 0, tzinfo=UTC)
    days: int = 7
    n_aircraft: int = 20
    min_turn: timedelta = timedelta(minutes=45)
    max_extra_turn_min: int = 60
    first_departure_local: time = time(6, 0)
    last_departure_local: time = time(21, 30)
    airports: tuple[AirportSpec, ...] = AIRPORTS

    @property
    def end(self) -> datetime:
        return self.start + timedelta(days=self.days)


@dataclass(frozen=True)
class AircraftSpec:
    id: str
    fleet_type: str
    home_base: str
    initial_station: str


@dataclass(frozen=True)
class FlightSpec:
    id: str
    flight_number: str
    aircraft_id: str
    origin: str
    destination: str
    departure: datetime
    arrival: datetime
    cycles: int = 1


@dataclass(frozen=True)
class Schedule:
    config: ScheduleConfig
    aircraft: tuple[AircraftSpec, ...]
    flights: tuple[FlightSpec, ...] = field(repr=False)


def great_circle_miles(a: AirportSpec, b: AirportSpec) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (a.latitude, a.longitude, b.latitude, b.longitude))
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * 3958.8 * math.asin(math.sqrt(h))


def block_time(a: AirportSpec, b: AirportSpec) -> timedelta:
    minutes = 35 + great_circle_miles(a, b) / 7.5  # 450 mph = 7.5 miles per minute
    return timedelta(minutes=5 * math.ceil(minutes / 5))


def local_at(day: date, clock: time, tz: str) -> datetime:
    """UTC instant of a local wall-clock time at an airport."""
    return datetime.combine(day, clock, tzinfo=ZoneInfo(tz)).astimezone(UTC)


def _round_up_5(t: datetime) -> datetime:
    extra = (-t.minute) % 5
    return (t + timedelta(minutes=extra)).replace(second=0, microsecond=0)


def generate_schedule(config: ScheduleConfig | None = None) -> Schedule:
    cfg = config or ScheduleConfig()
    airports = {a.code: a for a in cfg.airports}
    hubs = [a.code for a in cfg.airports if a.is_hub]
    if not hubs:
        raise ValueError("at least one hub is required")
    if cfg.n_aircraft > 99:
        raise ValueError("flight numbering supports at most 99 aircraft")

    aircraft: list[AircraftSpec] = []
    flights: list[FlightSpec] = []
    for index in range(cfg.n_aircraft):
        rng = random.Random(f"{cfg.seed}:{index}")
        ship = str(801 + index)
        home = hubs[index % len(hubs)]
        aircraft.append(AircraftSpec(ship, FLEET_TYPE, home, home))

        station = home
        ready = cfg.start  # the loop moves this to the station's first local departure slot
        legs_per_day: dict[date, int] = {}
        while True:
            tz = airports[station].timezone
            local_ready = ready.astimezone(ZoneInfo(tz))
            day_open = local_at(local_ready.date(), cfg.first_departure_local, tz)
            day_close = local_at(local_ready.date(), cfg.last_departure_local, tz)
            if ready < day_open:
                departure = day_open + timedelta(minutes=5 * rng.randint(0, 12))
            elif ready > day_close:  # overnight at this station
                next_day = local_ready.date() + timedelta(days=1)
                departure = local_at(next_day, cfg.first_departure_local, tz) + timedelta(
                    minutes=5 * rng.randint(0, 12)
                )
            else:
                departure = _round_up_5(ready)
            if departure >= cfg.end:
                break

            if station in hubs:
                destination = rng.choice([c for c in airports if c != station])
            else:
                destination = rng.choice(hubs)
            arrival = departure + block_time(airports[station], airports[destination])

            local_day = departure.astimezone(ZoneInfo(tz)).date()
            leg = legs_per_day.get(local_day, 0)
            legs_per_day[local_day] = leg + 1
            number = f"NS{1000 + index * 10 + leg}"
            flights.append(
                FlightSpec(
                    id=f"{number}-{local_day:%Y%m%d}",
                    flight_number=number,
                    aircraft_id=ship,
                    origin=station,
                    destination=destination,
                    departure=departure,
                    arrival=arrival,
                )
            )
            station = destination
            ready = (
                arrival
                + cfg.min_turn
                + timedelta(minutes=5 * rng.randint(0, cfg.max_extra_turn_min // 5))
            )

    flights.sort(key=lambda f: (f.departure, f.aircraft_id))
    return Schedule(cfg, tuple(aircraft), tuple(flights))
