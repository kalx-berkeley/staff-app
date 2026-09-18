"""replace surfaced_spin_matches with dismissed_spin_matches

Revision ID: 5f2b6e8a1c4d
Revises: 3e6b9f1c7d2a
Create Date: 2026-09-18 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "5f2b6e8a1c4d"
down_revision: Union[str, None] = "3e6b9f1c7d2a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index(
        op.f("ix_surfaced_spin_matches_surfaced_at"), table_name="surfaced_spin_matches"
    )
    op.drop_table("surfaced_spin_matches")
    op.create_table(
        "dismissed_spin_matches",
        sa.Column("spin_id", sa.BigInteger(), nullable=False),
        sa.Column("show_id", sa.Integer(), nullable=False),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("spin_id", "show_id"),
    )
    op.create_index(
        op.f("ix_dismissed_spin_matches_dismissed_at"),
        "dismissed_spin_matches",
        ["dismissed_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_dismissed_spin_matches_dismissed_at"), table_name="dismissed_spin_matches"
    )
    op.drop_table("dismissed_spin_matches")
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
