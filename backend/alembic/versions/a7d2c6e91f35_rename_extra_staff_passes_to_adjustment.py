"""rename shows.extra_staff_passes to staff_pass_adjustment

A show can now have fewer staff passes than the usual one per pass pair as
well as more, so the value is a signed adjustment rather than an "extra" count.

Revision ID: a7d2c6e91f35
Revises: f5c8b2e6a0d3
Create Date: 2026-11-04 18:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "a7d2c6e91f35"
down_revision: Union[str, None] = "f5c8b2e6a0d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("shows") as batch_op:
        batch_op.alter_column(
            "extra_staff_passes",
            new_column_name="staff_pass_adjustment",
            existing_type=sa.Integer(),
            existing_nullable=False,
            existing_server_default=sa.text("0"),
        )


def downgrade() -> None:
    with op.batch_alter_table("shows") as batch_op:
        batch_op.alter_column(
            "staff_pass_adjustment",
            new_column_name="extra_staff_passes",
            existing_type=sa.Integer(),
            existing_nullable=False,
            existing_server_default=sa.text("0"),
        )
