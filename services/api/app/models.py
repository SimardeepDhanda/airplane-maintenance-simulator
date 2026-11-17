"""ORM models. Timestamps are timezone-aware and stored in UTC.

Everything except `engine_observations` values and `model_versions` content is synthetic
(fictional airline). Observations are copied verbatim from NASA C-MAPSS test trajectories.
"""

from __future__ import annotations

from datetime import datetime
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
