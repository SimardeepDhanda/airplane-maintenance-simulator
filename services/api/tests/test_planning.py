from datetime import UTC, datetime, timedelta

import pytest

from app.services.planning import Leg, assess, classify

T0 = datetime(2027, 3, 11, 12, tzinfo=UTC)


def _legs(n: int) -> list[Leg]:
    return [Leg(f"F{i:02d}", T0 + timedelta(hours=3 * i), 1) for i in range(n)]


def test_margins_subtract_forecast_cycles() -> None:
    a = assess(rul_point=50, rul_lower=40, legs=_legs(12), buffer=10)
    assert (a.forecast_legs, a.forecast_cycles) == (12, 12)
    assert a.margin == 38 and a.conservative_margin == 28
    assert a.status == "ok" and a.flagged_flight_ids == ()


def test_first_flagged_flight_is_where_buffer_is_crossed() -> None:
    a = assess(rul_point=30, rul_lower=20, legs=_legs(15), buffer=10)
    # after leg k (1-based) conservative margin = 20 - k; < 10 from k = 11
    assert a.first_flagged_flight_id == "F10"
    assert a.flagged_flight_ids == ("F10", "F11", "F12", "F13", "F14")
    assert a.status == "review"


def test_critical_when_legs_exceed_lower_bound() -> None:
    a = assess(rul_point=12, rul_lower=5, legs=_legs(8), buffer=3)
    assert a.conservative_margin == -3 and a.status == "critical"


def test_unordered_input_and_multi_cycle_legs() -> None:
    legs = [Leg("B", T0 + timedelta(hours=5), 2), Leg("A", T0, 1)]
    a = assess(10, 4, legs, buffer=2)
    assert a.forecast_cycles == 3
    assert a.flagged_flight_ids == ("B",)


def test_no_legs() -> None:
    a = assess(10, 4, [], buffer=5)
    assert a.status == "review" and a.first_flagged_flight_id is None


@pytest.mark.parametrize(
    ("margin", "buffer", "status"),
    [(-0.5, 10, "critical"), (0, 10, "review"), (9.9, 10, "review"), (10, 10, "ok"), (0, 0, "ok")],
)
def test_classify_boundaries(margin: float, buffer: int, status: str) -> None:
    assert classify(margin, buffer) == status


def test_negative_buffer_rejected() -> None:
    with pytest.raises(ValueError):
        assess(10, 5, [], buffer=-1)
