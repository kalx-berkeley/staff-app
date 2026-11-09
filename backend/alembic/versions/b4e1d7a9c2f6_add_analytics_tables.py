"""add analytics_event and analytics_daily_count

The tracking tables for KALX Staff Analytics.

Revision ID: b4e1d7a9c2f6
Revises: a7d2c6e91f35
Create Date: 2026-11-09 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "b4e1d7a9c2f6"
down_revision: Union[str, None] = "a7d2c6e91f35"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "analytics_event",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("area", sa.String(), nullable=False),
        sa.Column("actor_email", sa.String(), nullable=True),
        sa.Column("network", sa.String(), nullable=True),
        sa.Column("ref", sa.String(length=64), nullable=True),
        sa.Column("entity_type", sa.String(), nullable=True),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("dj_name", sa.String(), nullable=True),
        sa.Column("dimension", sa.String(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_analytics_event_id", "analytics_event", ["id"])
    op.create_index("ix_analytics_event_occurred_at", "analytics_event", ["occurred_at"])
    op.create_index("ix_analytics_event_event_type", "analytics_event", ["event_type"])
    op.create_index("ix_analytics_event_ref", "analytics_event", ["ref"])
    op.create_index(
        "ix_analytics_event_type_occurred", "analytics_event", ["event_type", "occurred_at"]
    )

    op.create_table(
        "analytics_daily_count",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("area", sa.String(), nullable=False),
        sa.Column("actor_email", sa.String(), nullable=True),
        sa.Column("network", sa.String(), nullable=True),
        sa.Column("entity_type", sa.String(), nullable=True),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("dj_name", sa.String(), nullable=True),
        sa.Column("dimension", sa.String(), nullable=True),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "day",
            "event_type",
            "area",
            "actor_email",
            "network",
            "entity_type",
            "entity_id",
            "dj_name",
            "dimension",
            name="uq_analytics_daily_count_key",
        ),
    )
    op.create_index("ix_analytics_daily_count_id", "analytics_daily_count", ["id"])
    op.create_index("ix_analytics_daily_count_day", "analytics_daily_count", ["day"])
    op.create_index(
        "ix_analytics_daily_count_event_type", "analytics_daily_count", ["event_type"]
    )


def downgrade() -> None:
    op.drop_table("analytics_daily_count")
    op.drop_table("analytics_event")
