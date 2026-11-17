"""Fleet schema: airports, aircraft, engines, observations, predictions, model versions, flights.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "airports",
        sa.Column("code", sa.String(length=3), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("city", sa.String(length=80), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("is_hub", sa.Boolean(), nullable=False),
        sa.Column("has_maintenance_base", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("code"),
    )
    op.create_table(
        "model_versions",
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("data_kind", sa.String(length=32), nullable=False),
        sa.Column("subset", sa.String(length=8), nullable=False),
        sa.Column("trained_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("manifest", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "data_kind IN ('nasa_cmapss', 'synthetic_fixture')", name="model_versions_data_kind"
        ),
        sa.PrimaryKeyConstraint("version"),
    )
    op.create_index(
        "uq_model_versions_active",
        "model_versions",
        ["is_active"],
        unique=True,
        postgresql_where="is_active",
    )
    op.create_table(
        "simulations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("generator_version", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "aircraft",
        sa.Column("id", sa.String(length=16), nullable=False),
        sa.Column("fleet_type", sa.String(length=32), nullable=False),
        sa.Column("home_base", sa.String(length=3), nullable=False),
        sa.Column("initial_station", sa.String(length=3), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.CheckConstraint("status IN ('active', 'grounded')", name="aircraft_status"),
        sa.ForeignKeyConstraint(
            ["home_base"],
            ["airports.code"],
        ),
        sa.ForeignKeyConstraint(
            ["initial_station"],
            ["airports.code"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "engines",
        sa.Column("id", sa.String(length=16), nullable=False),
        sa.Column("aircraft_id", sa.String(length=16), nullable=True),
        sa.Column("source_dataset", sa.String(length=32), nullable=False),
        sa.Column("source_subset", sa.String(length=8), nullable=False),
        sa.Column("source_split", sa.String(length=8), nullable=False),
        sa.Column("source_unit_id", sa.Integer(), nullable=False),
        sa.Column("observed_through_cycle", sa.Integer(), nullable=False),
        sa.Column("eval_true_rul", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["aircraft_id"],
            ["aircraft.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("aircraft_id"),
        sa.UniqueConstraint(
            "source_subset", "source_split", "source_unit_id", name="uq_engine_source"
        ),
    )
    op.create_table(
        "flights",
        sa.Column("id", sa.String(length=24), nullable=False),
        sa.Column("flight_number", sa.String(length=8), nullable=False),
        sa.Column("aircraft_id", sa.String(length=16), nullable=False),
        sa.Column("origin", sa.String(length=3), nullable=False),
        sa.Column("destination", sa.String(length=3), nullable=False),
        sa.Column("scheduled_departure", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scheduled_arrival", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("cycles", sa.Integer(), nullable=False),
        sa.CheckConstraint("status IN ('scheduled', 'cancelled')", name="flight_status"),
        sa.CheckConstraint("cycles >= 1", name="flight_cycles"),
        sa.CheckConstraint("origin <> destination", name="flight_route"),
        sa.CheckConstraint("scheduled_arrival > scheduled_departure", name="flight_times"),
        sa.ForeignKeyConstraint(
            ["aircraft_id"],
            ["aircraft.id"],
        ),
        sa.ForeignKeyConstraint(
            ["destination"],
            ["airports.code"],
        ),
        sa.ForeignKeyConstraint(
            ["origin"],
            ["airports.code"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_flights_aircraft_departure",
        "flights",
        ["aircraft_id", "scheduled_departure"],
        unique=False,
    )
    op.create_index("ix_flights_departure", "flights", ["scheduled_departure"], unique=False)
    op.create_table(
        "engine_observations",
        sa.Column("engine_id", sa.String(length=16), nullable=False),
        sa.Column("cycle", sa.Integer(), nullable=False),
        sa.Column("settings", sa.ARRAY(sa.Float(), dimensions=1), nullable=False),
        sa.Column("sensors", sa.ARRAY(sa.Float(), dimensions=1), nullable=False),
        sa.CheckConstraint("array_length(sensors, 1) = 21", name="obs_sensors_len"),
        sa.CheckConstraint("array_length(settings, 1) = 3", name="obs_settings_len"),
        sa.ForeignKeyConstraint(["engine_id"], ["engines.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("engine_id", "cycle"),
    )
    op.create_table(
        "engine_predictions",
        sa.Column("engine_id", sa.String(length=16), nullable=False),
        sa.Column("cycle", sa.Integer(), nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.Column("rul_point", sa.Float(), nullable=False),
        sa.Column("rul_lower", sa.Float(), nullable=False),
        sa.Column("rul_upper", sa.Float(), nullable=False),
        sa.CheckConstraint("rul_lower <= rul_point AND rul_point <= rul_upper", name="pred_order"),
        sa.ForeignKeyConstraint(
            ["engine_id", "cycle"],
            ["engine_observations.engine_id", "engine_observations.cycle"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["model_version"],
            ["model_versions.version"],
        ),
        sa.PrimaryKeyConstraint("engine_id", "cycle", "model_version"),
    )


def downgrade() -> None:
    op.drop_table("engine_predictions")
    op.drop_table("engine_observations")
    op.drop_index("ix_flights_departure", table_name="flights")
    op.drop_index("ix_flights_aircraft_departure", table_name="flights")
    op.drop_table("flights")
    op.drop_table("engines")
    op.drop_table("aircraft")
    op.drop_table("simulations")
    op.drop_index(
        "uq_model_versions_active", table_name="model_versions", postgresql_where="is_active"
    )
    op.drop_table("model_versions")
    op.drop_table("airports")
