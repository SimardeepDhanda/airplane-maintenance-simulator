"""API response models. RUL values are engine cycles; timestamps are UTC unless suffixed _local."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

PlanningStatus = Literal["ok", "review", "critical"]


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    database: Literal["ok", "unavailable"]
    version: str


class Page[T](BaseModel):
    items: list[T]
    total: int
    page: int
    page_size: int


class AirportOut(BaseModel):
    code: str
    name: str
    city: str
    timezone: str
    is_hub: bool
    has_maintenance_base: bool


class PredictionOut(BaseModel):
    rul_point: float
    rul_lower: float
    rul_upper: float
    model_version: str
    observed_through_cycle: int


class PlanningOut(BaseModel):
    forecast_legs: int
    forecast_cycles: int
    margin: float = Field(description="Predicted RUL minus forecast cycles")
    conservative_margin: float = Field(description="Lower bound minus forecast cycles")
    status: PlanningStatus
    buffer: int
    first_flagged_flight_id: str | None
    first_flagged_departure: datetime | None


class EngineSummary(BaseModel):
    id: str
    aircraft_id: str | None
    station: str | None = Field(description="Aircraft location at the simulation start")
    observed_cycles: int
    prediction: PredictionOut
    planning: PlanningOut


class ProvenanceOut(BaseModel):
    dataset: str
    subset: str
    split: str
    unit_id: int
    data_kind: str
    eval_true_rul: int | None = Field(
        description="NASA ground truth at the last observed cycle. Evaluation context only."
    )


class FlightOut(BaseModel):
    id: str
    flight_number: str
    aircraft_id: str
    engine_id: str | None
    origin: str
    destination: str
    departure: datetime
    arrival: datetime
    departure_local: datetime
    arrival_local: datetime
    origin_tz: str
    destination_tz: str
    origin_tz_abbr: str
    destination_tz_abbr: str
    status: str
    cycles: int
    cumulative_cycles: int = Field(
        description="Cycles this aircraft flies from the start through this leg"
    )
    conservative_margin_after: float | None = Field(
        description="Engine lower-bound RUL minus cumulative cycles after this leg"
    )
    flagged: bool


class EngineDetail(EngineSummary):
    fleet_type: str | None
    home_base: str | None
    provenance: ProvenanceOut
    flights: list[FlightOut]


class SeriesOut(BaseModel):
    name: str
    values: list[float]


class EngineHistory(BaseModel):
    engine_id: str
    model_version: str
    cycles: list[int]
    sensors: list[SeriesOut]
    rul_point: list[float]
    rul_lower: list[float]
    rul_upper: list[float]


class StatusCounts(BaseModel):
    ok: int
    review: int
    critical: int


class ModelRef(BaseModel):
    version: str
    data_kind: str
    subset: str
    trained_at: datetime


class FleetSummary(BaseModel):
    as_of: datetime
    horizon_end: datetime
    aircraft: int
    engines: int
    flights: int
    planning_buffer: int
    status_counts: StatusCounts
    model: ModelRef


class ModelMetrics(BaseModel):
    model: ModelRef
    selection: dict[str, Any]
    test: dict[str, Any]
    permutation_importance: dict[str, Any]
    features: dict[str, Any]
    conformal: dict[str, Any]
    split: dict[str, Any]
