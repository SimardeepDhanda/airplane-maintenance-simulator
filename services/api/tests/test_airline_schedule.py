"""Invariants of the generated fictional schedule. No database needed."""

from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta
from itertools import pairwise
from zoneinfo import ZoneInfo

import pytest

from app.simulation.airline import (
    AIRPORTS,
    FlightSpec,
    ScheduleConfig,
    block_time,
    generate_schedule,
    local_at,
)

SCHEDULE = generate_schedule()
AIRPORT = {a.code: a for a in AIRPORTS}
HUBS = {a.code for a in AIRPORTS if a.is_hub}


def _by_aircraft(flights: tuple[FlightSpec, ...]) -> dict[str, list[FlightSpec]]:
    out: dict[str, list[FlightSpec]] = defaultdict(list)
    for f in flights:
        out[f.aircraft_id].append(f)
    for legs in out.values():
        legs.sort(key=lambda f: f.departure)
    return out


def test_generation_is_deterministic() -> None:
    assert generate_schedule() == SCHEDULE
    assert generate_schedule(ScheduleConfig(seed=1)) != SCHEDULE


def test_every_aircraft_flies_and_ids_are_unique() -> None:
    legs = _by_aircraft(SCHEDULE.flights)
    assert set(legs) == {a.id for a in SCHEDULE.aircraft}
    assert len({f.id for f in SCHEDULE.flights}) == len(SCHEDULE.flights)
    assert all(f.cycles == 1 for f in SCHEDULE.flights)


def test_no_overlapping_flights_and_minimum_turn() -> None:
    cfg = SCHEDULE.config
    for legs in _by_aircraft(SCHEDULE.flights).values():
        for prev, nxt in pairwise(legs):
            assert nxt.departure - prev.arrival >= cfg.min_turn


def test_location_continuity() -> None:
    for aircraft in SCHEDULE.aircraft:
        legs = _by_aircraft(SCHEDULE.flights)[aircraft.id]
        assert legs[0].origin == aircraft.initial_station
        for prev, nxt in pairwise(legs):
            assert nxt.origin == prev.destination


def test_routes_are_hub_and_spoke_with_consistent_block_times() -> None:
    for f in SCHEDULE.flights:
        assert f.origin != f.destination
        assert f.origin in HUBS or f.destination in HUBS
        assert f.arrival - f.departure == block_time(AIRPORT[f.origin], AIRPORT[f.destination])


def test_departures_within_local_operating_hours_and_horizon() -> None:
    cfg = SCHEDULE.config
    for f in SCHEDULE.flights:
        local = f.departure.astimezone(ZoneInfo(AIRPORT[f.origin].timezone)).time()
        assert cfg.first_departure_local <= local <= cfg.last_departure_local
        assert cfg.start <= f.departure < cfg.end
        assert f.departure.tzinfo is not None
        assert f.departure.minute % 5 == 0


def test_forecast_cycles_equal_leg_count() -> None:
    legs = _by_aircraft(SCHEDULE.flights)
    for aircraft_id, aircraft_legs in legs.items():
        assert sum(f.cycles for f in aircraft_legs) == len(aircraft_legs)
        assert 10 <= len(aircraft_legs) <= 50, aircraft_id


def test_dst_transition_keeps_local_opening_time() -> None:
    # 2027-03-14: US clocks spring forward. Phoenix does not observe DST.
    before, after = date(2027, 3, 13), date(2027, 3, 15)
    chicago_before = local_at(before, time(6, 0), "America/Chicago")
    chicago_after = local_at(after, time(6, 0), "America/Chicago")
    assert chicago_before == datetime(2027, 3, 13, 12, 0, tzinfo=UTC)  # CST, UTC-6
    assert chicago_after == datetime(2027, 3, 15, 11, 0, tzinfo=UTC)  # CDT, UTC-5
    phoenix = [local_at(d, time(6, 0), "America/Phoenix") for d in (before, after)]
    assert phoenix[1] - phoenix[0] == timedelta(days=2)  # MST all year, no shift


def test_schedule_spans_dst_change() -> None:
    cfg = SCHEDULE.config
    assert cfg.start < datetime(2027, 3, 14, 8, 0, tzinfo=UTC) < cfg.end
    after_change = [f for f in SCHEDULE.flights if f.departure > datetime(2027, 3, 15, tzinfo=UTC)]
    assert after_change


def test_flight_ids_use_origin_local_date() -> None:
    for f in SCHEDULE.flights:
        local_day = f.departure.astimezone(ZoneInfo(AIRPORT[f.origin].timezone)).date()
        assert f.id == f"{f.flight_number}-{local_day:%Y%m%d}"


@pytest.mark.parametrize("n", [1, 5])
def test_small_fleets(n: int) -> None:
    schedule = generate_schedule(ScheduleConfig(n_aircraft=n, days=2))
    assert len(schedule.aircraft) == n
    assert {f.aircraft_id for f in schedule.flights} == {a.id for a in schedule.aircraft}
