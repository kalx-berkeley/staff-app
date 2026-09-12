"""add staff_genre_preferences table

Revision ID: 07bbdf2b0518
Revises: d324a3e601d7
Create Date: 2026-09-12 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "07bbdf2b0518"
down_revision: Union[str, None] = "d324a3e601d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "staff_genre_preferences",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("staff_id", sa.Integer(), nullable=False),
        sa.Column("genres", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["staff_id"], ["staff.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("staff_id", name="uq_staff_genre_preferences_staff_id"),
    )
    op.create_index(
        op.f("ix_staff_genre_preferences_id"),
        "staff_genre_preferences",
        ["id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_staff_genre_preferences_id"), table_name="staff_genre_preferences"
    )
    op.drop_table("staff_genre_preferences")
