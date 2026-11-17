"""API response models. RUL values are engine cycles; timestamps are UTC unless suffixed _local."""

from datetime import datetime, time
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


# --- Maintenance planning (Phase 4). Costs are fictional integer units. ---

JobType = Literal["engine_change", "borescope"]
ThresholdPolicy = Literal["penalty", "hard"]
MethodStatus = Literal["OPTIMAL", "FEASIBLE", "INFEASIBLE", "UNKNOWN", "NO_SOLUTION"]


class JobTypeOut(BaseModel):
    id: JobType
    label: str
    duration_hours: int
    technicians: int
    part_type: str | None


class ShiftOut(BaseModel):
    name: str
    start_local: time
    end_local: time
    technicians: int
    is_night: bool


class BayOut(BaseModel):
    id: str
    name: str


class FacilityOut(BaseModel):
    code: str
    name: str
    kind: Literal["hangar", "line"]
    timezone: str
    supports: list[JobType]
    bays: list[BayOut]
    shifts: list[ShiftOut]


class PartLotOut(BaseModel):
    id: str
    part_type: str
    location: str
    quantity: int
    available_at: datetime
    transfer_lead_hours: int


class MaintenanceResources(BaseModel):
    horizon_start: datetime
    horizon_end: datetime
    facilities: list[FacilityOut]
    parts: list[PartLotOut]
    job_types: list[JobTypeOut]


class JobOut(BaseModel):
    id: str
    engine_id: str | None
    aircraft_id: str
    job_type: JobType
    reason: Literal["critical", "review", "added"]
    duration_hours: int
    technicians: int
    part_type: str | None
    due_flight_id: str | None
    due_at: datetime | None


class PlacementOut(BaseModel):
    job_id: str
    engine_id: str | None
    aircraft_id: str
    job_type: JobType
    reason: str
    facility: str
    bay: str
    start: datetime
    end: datetime
    start_local: datetime
    end_local: datetime
    tz_abbr: str
    cancelled_flights: list[str]
    cycles_over: int
    part_lot: str | None
    part_from: str | None
    labor_hours: int
    why: list[str]


class UnscheduledOut(BaseModel):
    job_id: str
    engine_id: str | None
    aircraft_id: str
    job_type: JobType
    reason: str
    cycles_over: int
    why: str


class ExplanationOut(BaseModel):
    job_id: str | None
    code: str
    message: str


class CostsOut(BaseModel):
    cancellations: int
    threshold: int
    unscheduled: int
    labor: int
    transfers: int
    total: int


class PlanMetricsOut(BaseModel):
    jobs_total: int
    jobs_scheduled: int
    jobs_unscheduled: int
    thresholds_missed: int
    cycles_over_threshold: int
    cancelled_legs: int
    grounded_legs: int
    labor_hours: int
    part_transfers: int
    bay_utilization: float


class PlanOut(BaseModel):
    method: Literal["baseline", "optimized"]
    status: MethodStatus
    objective: int | None
    best_bound: float | None
    wall_ms: int
    costs: CostsOut | None
    metrics: PlanMetricsOut | None
    placements: list[PlacementOut]
    unscheduled: list[UnscheduledOut]
    explanations: list[ExplanationOut]
    verified: bool  # independent constraint check found no violations
    jobs: list[JobOut]


class AddedJob(BaseModel):
    aircraft_id: str = Field(max_length=16)
    job_type: JobType


class ScenarioAssumptions(BaseModel):
    buffer: int = Field(default=10, ge=0, le=200)
    threshold_policy: ThresholdPolicy = "penalty"
    bay_changes: dict[str, int] = Field(
        default_factory=dict, description="Facility code -> change in bay count"
    )
    part_delay_hours: int = Field(default=0, ge=0, le=168)
    grounded_aircraft: list[str] = Field(default_factory=list, max_length=5)
    added_jobs: list[AddedJob] = Field(default_factory=list, max_length=5)
    time_limit_s: float = Field(default=10.0, ge=0.5, le=30.0)


class ScenarioCreate(BaseModel):
    name: str | None = Field(default=None, max_length=80)
    assumptions: ScenarioAssumptions = Field(default_factory=ScenarioAssumptions)


class ComparisonRow(BaseModel):
    key: str
    label: str
    unit: str
    baseline: float | None
    optimized: float | None
    delta: float | None
    pct_change: float | None  # None when undefined (baseline 0 or a side has no plan)
    better: Literal["lower", "higher"] | None


class ScenarioOut(BaseModel):
    id: int
    name: str
    status: Literal["created", "queued", "running", "solved", "failed"]
    error: str | None
    created_at: datetime
    updated_at: datetime
    assumptions: ScenarioAssumptions
    baseline: PlanOut | None
    optimized: PlanOut | None
    comparison: list[ComparisonRow]


class ScenarioSummaryOut(BaseModel):
    id: int
    name: str
    status: str
    created_at: datetime
    baseline_status: str | None
    optimized_status: str | None
