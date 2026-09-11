"""add spin match tables

Revision ID: 269a20ccdde6
Revises: 88321f994b58
Create Date: 2026-09-11 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "269a20ccdde6"
down_revision: Union[str, None] = "88321f994b58"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "spinitron_spin_cache",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("spins", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "surfaced_spin_matches",
        sa.Column("spin_id", sa.BigInteger(), nullable=False),
        sa.Column("show_id", sa.Integer(), nullable=False),
        sa.Column("surfaced_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("spin_id"),
    )
    op.create_index(
        op.f("ix_surfaced_spin_matches_surfaced_at"),
        "surfaced_spin_matches",
        ["surfaced_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_surfaced_spin_matches_surfaced_at"), table_name="surfaced_spin_matches"
    )
    op.drop_table("surfaced_spin_matches")
    op.drop_table("spinitron_spin_cache")
