"""workform work types

Adds the types of work department heads can offer staff logging hours in
their department, and whether staff may describe other work in their own
words.

Revision ID: c9f1a3e5b7d2
Revises: b8e4c1d7a9f2
Create Date: 2026-10-21 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "c9f1a3e5b7d2"
down_revision: Union[str, None] = "b8e4c1d7a9f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workform_work_types",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("department", sa.String(), nullable=False),
        sa.Column("work_types", sa.JSON(), nullable=False),
        sa.Column(
            "allow_free_text", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("department"),
    )
    op.create_index("ix_workform_work_types_id", "workform_work_types", ["id"])


def downgrade() -> None:
    op.drop_index("ix_workform_work_types_id", table_name="workform_work_types")
    op.drop_table("workform_work_types")
