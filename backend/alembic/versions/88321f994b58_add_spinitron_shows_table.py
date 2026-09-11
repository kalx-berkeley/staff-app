"""add spinitron_shows table

Revision ID: 88321f994b58
Revises: 1567a07a55b6
Create Date: 2026-09-11 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "88321f994b58"
down_revision: Union[str, None] = "1567a07a55b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "spinitron_shows",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("dj_name", sa.String(), nullable=True),
        sa.Column("persona_id", sa.Integer(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_spinitron_shows_start"), "spinitron_shows", ["start"], unique=False
    )
    op.create_index(
        op.f("ix_spinitron_shows_end"), "spinitron_shows", ["end"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_spinitron_shows_end"), table_name="spinitron_shows")
    op.drop_index(op.f("ix_spinitron_shows_start"), table_name="spinitron_shows")
    op.drop_table("spinitron_shows")
