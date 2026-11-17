"""ORM models. Timestamps are timezone-aware and stored in UTC.

Everything except `engine_observations` values and `model_versions` content is synthetic
(fictional airline). Observations are copied verbatim from NASA C-MAPSS test trajectories.
"""

from __future__ import annotations

from datetime import datetime, time
from typing import Any

from sqlalchemy import (
    ARRAY,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Time,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Airport(Base):
    __tablename__ = "airports"

    code: Mapped[str] = mapped_column(String(3), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    city: Mapped[str] = mapped_column(String(80))
    timezone: Mapped[str] = mapped_column(String(64))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    is_hub: Mapped[bool] = mapped_column(Boolean, default=False)
    has_maintenance_base: Mapped[bool] = mapped_column(Boolean, default=False)


class Simulation(Base):
    """Parameters of the seeded fictional schedule (one active row)."""

    __tablename__ = "simulations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    seed: Mapped[int] = mapped_column(Integer)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    generator_version: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Aircraft(Base):
    __tablename__ = "aircraft"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)  # fictional ship number
    fleet_type: Mapped[str] = mapped_column(String(32))
    home_base: Mapped[str] = mapped_column(ForeignKey("airports.code"))
    initial_station: Mapped[str] = mapped_column(ForeignKey("airports.code"))
    status: Mapped[str] = mapped_column(String(16), default="active")

    engine: Mapped[Engine | None] = relationship(back_populates="aircraft")

    __table_args__ = (CheckConstraint("status IN ('active', 'grounded')", name="aircraft_status"),)


class ModelVersion(Base):
    __tablename__ = "model_versions"

    version: Mapped[str] = mapped_column(String(64), primary_key=True)
    data_kind: Mapped[str] = mapped_column(String(32))
    subset: Mapped[str] = mapped_column(String(8))
    trained_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    manifest: Mapped[dict[str, Any]] = mapped_column(JSONB)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (
        CheckConstraint(
            "data_kind IN ('nasa_cmapss', 'synthetic_fixture')", name="model_versions_data_kind"
        ),
        # At most one active model.
        Index("uq_model_versions_active", "is_active", unique=True, postgresql_where="is_active"),
    )


class Engine(Base):
    __tablename__ = "engines"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    aircraft_id: Mapped[str | None] = mapped_column(ForeignKey("aircraft.id"), unique=True)
    source_dataset: Mapped[str] = mapped_column(String(32))  # "NASA C-MAPSS"
    source_subset: Mapped[str] = mapped_column(String(8))  # "FD001"
    source_split: Mapped[str] = mapped_column(String(8))  # "test"
    source_unit_id: Mapped[int] = mapped_column(Integer)
    observed_through_cycle: Mapped[int] = mapped_column(Integer)
    # Ground truth from RUL_FD001.txt. Shown only as evaluation context, never used for planning.
    eval_true_rul: Mapped[int | None] = mapped_column(Integer)

    aircraft: Mapped[Aircraft | None] = relationship(back_populates="engine")

    __table_args__ = (
        UniqueConstraint(
            "source_subset", "source_split", "source_unit_id", name="uq_engine_source"
        ),
    )


class EngineObservation(Base):
    __tablename__ = "engine_observations"

    engine_id: Mapped[str] = mapped_column(
        ForeignKey("engines.id", ondelete="CASCADE"), primary_key=True
    )
    cycle: Mapped[int] = mapped_column(Integer, primary_key=True)
    settings: Mapped[list[float]] = mapped_column(ARRAY(Float, dimensions=1))  # 3 values
    sensors: Mapped[list[float]] = mapped_column(ARRAY(Float, dimensions=1))  # 21 values

    __table_args__ = (
        CheckConstraint("array_length(settings, 1) = 3", name="obs_settings_len"),
        CheckConstraint("array_length(sensors, 1) = 21", name="obs_sensors_len"),
    )


class EnginePrediction(Base):
    __tablename__ = "engine_predictions"

    engine_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    cycle: Mapped[int] = mapped_column(Integer, primary_key=True)
    model_version: Mapped[str] = mapped_column(
        ForeignKey("model_versions.version"), primary_key=True
    )
    rul_point: Mapped[float] = mapped_column(Float)
    rul_lower: Mapped[float] = mapped_column(Float)
    rul_upper: Mapped[float] = mapped_column(Float)

    __table_args__ = (
        ForeignKeyConstraint(
            ["engine_id", "cycle"],
            ["engine_observations.engine_id", "engine_observations.cycle"],
            ondelete="CASCADE",
        ),
        CheckConstraint("rul_lower <= rul_point AND rul_point <= rul_upper", name="pred_order"),
    )


class Flight(Base):
    __tablename__ = "flights"

    id: Mapped[str] = mapped_column(String(24), primary_key=True)  # e.g. NS1203-20270311
    flight_number: Mapped[str] = mapped_column(String(8))
    aircraft_id: Mapped[str] = mapped_column(ForeignKey("aircraft.id"))
    origin: Mapped[str] = mapped_column(ForeignKey("airports.code"))
    destination: Mapped[str] = mapped_column(ForeignKey("airports.code"))
    scheduled_departure: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    scheduled_arrival: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), default="scheduled")
    cycles: Mapped[int] = mapped_column(Integer, default=1)

    __table_args__ = (
        CheckConstraint("scheduled_arrival > scheduled_departure", name="flight_times"),
        CheckConstraint("origin <> destination", name="flight_route"),
        CheckConstraint("cycles >= 1", name="flight_cycles"),
        CheckConstraint("status IN ('scheduled', 'cancelled')", name="flight_status"),
        Index("ix_flights_aircraft_departure", "aircraft_id", "scheduled_departure"),
        Index("ix_flights_departure", "scheduled_departure"),
    )


# --- Maintenance resources and scenarios (Phase 4). All synthetic. ---


class MaintenanceFacility(Base):
    __tablename__ = "maintenance_facilities"

    code: Mapped[str] = mapped_column(ForeignKey("airports.code"), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    kind: Mapped[str] = mapped_column(String(16))  # hangar | line
    supports: Mapped[list[str]] = mapped_column(ARRAY(String(32), dimensions=1))

    __table_args__ = (CheckConstraint("kind IN ('hangar', 'line')", name="facility_kind"),)


class MaintenanceBay(Base):
    __tablename__ = "maintenance_bays"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)  # e.g. ORD-1
    facility_code: Mapped[str] = mapped_column(
        ForeignKey("maintenance_facilities.code", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(32))

    __table_args__ = (UniqueConstraint("facility_code", "name", name="uq_bay_name"),)


class TechnicianShift(Base):
    """Recurring daily roster in the facility's local time. end < start wraps past midnight."""

    __tablename__ = "technician_shifts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    facility_code: Mapped[str] = mapped_column(
        ForeignKey("maintenance_facilities.code", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(16))
    start_local: Mapped[time] = mapped_column(Time)
    end_local: Mapped[time] = mapped_column(Time)
    technicians: Mapped[int] = mapped_column(Integer)
    is_night: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (
        CheckConstraint("technicians >= 0", name="shift_technicians"),
        UniqueConstraint("facility_code", "name", name="uq_shift_name"),
    )


class PartInventory(Base):
    __tablename__ = "parts_inventory"

    id: Mapped[str] = mapped_column(String(24), primary_key=True)
    part_type: Mapped[str] = mapped_column(String(32))
    location: Mapped[str] = mapped_column(ForeignKey("airports.code"))
    quantity: Mapped[int] = mapped_column(Integer)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    transfer_lead_hours: Mapped[int] = mapped_column(Integer)

    __table_args__ = (
        CheckConstraint("quantity >= 0", name="part_quantity"),
        CheckConstraint("transfer_lead_hours >= 0", name="part_lead"),
    )


class MaintenanceJob(Base):
    """Open job cards for the default planning buffer, derived from planning flags at seed time."""

    __tablename__ = "maintenance_jobs"

    id: Mapped[str] = mapped_column(String(24), primary_key=True)  # e.g. MX-ENG-802
    engine_id: Mapped[str] = mapped_column(ForeignKey("engines.id", ondelete="CASCADE"))
    aircraft_id: Mapped[str] = mapped_column(ForeignKey("aircraft.id"))
    job_type: Mapped[str] = mapped_column(String(32))
    duration_hours: Mapped[int] = mapped_column(Integer)
    technicians: Mapped[int] = mapped_column(Integer)
    part_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reason: Mapped[str] = mapped_column(String(16))
    planning_buffer: Mapped[int] = mapped_column(Integer)
    due_flight_id: Mapped[str | None] = mapped_column(ForeignKey("flights.id"), nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="open")

    __table_args__ = (
        CheckConstraint("duration_hours > 0", name="job_duration"),
        CheckConstraint("technicians > 0", name="job_technicians"),
        CheckConstraint("reason IN ('critical', 'review', 'added')", name="job_reason"),
        CheckConstraint("status IN ('open', 'closed')", name="job_status"),
        UniqueConstraint("engine_id", name="uq_job_engine"),
        Index("ix_jobs_due", "due_at"),
    )


class Scenario(Base):
    __tablename__ = "scenarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(80))
    assumptions: Mapped[dict[str, Any]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(16), default="created")
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "status IN ('created', 'queued', 'running', 'solved', 'failed')",
            name="scenario_status",
        ),
        Index("ix_scenarios_created", "created_at"),
    )


class ScenarioResult(Base):
    """One planner's output for a scenario. Stores job inputs so results are reproducible."""

    __tablename__ = "scenario_results"

    scenario_id: Mapped[int] = mapped_column(
        ForeignKey("scenarios.id", ondelete="CASCADE"), primary_key=True
    )
    method: Mapped[str] = mapped_column(String(16), primary_key=True)  # baseline | optimized
    status: Mapped[str] = mapped_column(String(16))
    objective: Mapped[int | None] = mapped_column(Integer, nullable=True)
    best_bound: Mapped[float | None] = mapped_column(Float, nullable=True)
    wall_ms: Mapped[int] = mapped_column(Integer)
    result: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("method IN ('baseline', 'optimized')", name="result_method"),
        CheckConstraint(
            "status IN ('OPTIMAL', 'FEASIBLE', 'INFEASIBLE', 'UNKNOWN', 'NO_SOLUTION')",
            name="result_status",
        ),
    )
