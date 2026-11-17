"""Maintenance resources, job cards, scenarios and scenario results.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "scenarios",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("assumptions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("error", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('created', 'queued', 'running', 'solved', 'failed')", name="scenario_status"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scenarios_created", "scenarios", ["created_at"], unique=False)
    op.create_table(
        "maintenance_facilities",
        sa.Column("code", sa.String(length=3), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("supports", sa.ARRAY(sa.String(length=32), dimensions=1), nullable=False),
        sa.CheckConstraint("kind IN ('hangar', 'line')", name="facility_kind"),
        sa.ForeignKeyConstraint(
            ["code"],
            ["airports.code"],
        ),
        sa.PrimaryKeyConstraint("code"),
    )
    op.create_table(
        "parts_inventory",
        sa.Column("id", sa.String(length=24), nullable=False),
        sa.Column("part_type", sa.String(length=32), nullable=False),
        sa.Column("location", sa.String(length=3), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("transfer_lead_hours", sa.Integer(), nullable=False),
        sa.CheckConstraint("quantity >= 0", name="part_quantity"),
        sa.CheckConstraint("transfer_lead_hours >= 0", name="part_lead"),
        sa.ForeignKeyConstraint(
            ["location"],
            ["airports.code"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "scenario_results",
        sa.Column("scenario_id", sa.Integer(), nullable=False),
        sa.Column("method", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("objective", sa.Integer(), nullable=True),
        sa.Column("best_bound", sa.Float(), nullable=True),
        sa.Column("wall_ms", sa.Integer(), nullable=False),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("method IN ('baseline', 'optimized')", name="result_method"),
        sa.CheckConstraint(
            "status IN ('OPTIMAL', 'FEASIBLE', 'INFEASIBLE', 'UNKNOWN', 'NO_SOLUTION')",
            name="result_status",
        ),
        sa.ForeignKeyConstraint(["scenario_id"], ["scenarios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("scenario_id", "method"),
    )
    op.create_table(
        "maintenance_bays",
        sa.Column("id", sa.String(length=16), nullable=False),
        sa.Column("facility_code", sa.String(length=3), nullable=False),
        sa.Column("name", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["facility_code"], ["maintenance_facilities.code"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("facility_code", "name", name="uq_bay_name"),
    )
    op.create_table(
        "technician_shifts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("facility_code", sa.String(length=3), nullable=False),
        sa.Column("name", sa.String(length=16), nullable=False),
        sa.Column("start_local", sa.Time(), nullable=False),
        sa.Column("end_local", sa.Time(), nullable=False),
        sa.Column("technicians", sa.Integer(), nullable=False),
        sa.Column("is_night", sa.Boolean(), nullable=False),
        sa.CheckConstraint("technicians >= 0", name="shift_technicians"),
        sa.ForeignKeyConstraint(
            ["facility_code"], ["maintenance_facilities.code"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("facility_code", "name", name="uq_shift_name"),
    )
    op.create_table(
        "maintenance_jobs",
        sa.Column("id", sa.String(length=24), nullable=False),
        sa.Column("engine_id", sa.String(length=16), nullable=False),
        sa.Column("aircraft_id", sa.String(length=16), nullable=False),
        sa.Column("job_type", sa.String(length=32), nullable=False),
        sa.Column("duration_hours", sa.Integer(), nullable=False),
        sa.Column("technicians", sa.Integer(), nullable=False),
        sa.Column("part_type", sa.String(length=32), nullable=True),
        sa.Column("reason", sa.String(length=16), nullable=False),
        sa.Column("planning_buffer", sa.Integer(), nullable=False),
        sa.Column("due_flight_id", sa.String(length=24), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.CheckConstraint("reason IN ('critical', 'review', 'added')", name="job_reason"),
        sa.CheckConstraint("status IN ('open', 'closed')", name="job_status"),
        sa.CheckConstraint("duration_hours > 0", name="job_duration"),
        sa.CheckConstraint("technicians > 0", name="job_technicians"),
        sa.ForeignKeyConstraint(
            ["aircraft_id"],
            ["aircraft.id"],
        ),
        sa.ForeignKeyConstraint(
            ["due_flight_id"],
            ["flights.id"],
        ),
        sa.ForeignKeyConstraint(["engine_id"], ["engines.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("engine_id", name="uq_job_engine"),
    )
    op.create_index("ix_jobs_due", "maintenance_jobs", ["due_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_jobs_due", table_name="maintenance_jobs")
    op.drop_table("maintenance_jobs")
    op.drop_table("technician_shifts")
    op.drop_table("maintenance_bays")
    op.drop_table("scenario_results")
    op.drop_table("parts_inventory")
    op.drop_table("maintenance_facilities")
    op.drop_index("ix_scenarios_created", table_name="scenarios")
    op.drop_table("scenarios")
