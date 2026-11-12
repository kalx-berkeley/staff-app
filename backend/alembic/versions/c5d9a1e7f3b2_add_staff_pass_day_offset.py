"""add staff pass day offset

A few venues give staff passes for a different night than the on-air pass
pairs. For those venues, new shows are created as two shows, the staff show
this many days after (or before) the on-air show.

Revision ID: c5d9a1e7f3b2
Revises: e8b3c6f2a9d4
Create Date: 2026-11-12 20:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "c5d9a1e7f3b2"
down_revision: Union[str, None] = "e8b3c6f2a9d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("venues") as batch_op:
        batch_op.add_column(sa.Column("staff_pass_day_offset", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("venues") as batch_op:
        batch_op.drop_column("staff_pass_day_offset")
