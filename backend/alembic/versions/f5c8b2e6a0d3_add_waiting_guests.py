"""add waiting guests to passes

A staff member's +1 guest can wait on the alternate list. The guest stays on
their host's pass row, marked as waiting, and guest_priority_at decides both
which guest gets a free pass first and which is bumped last.

Revision ID: f5c8b2e6a0d3
Revises: e3a7c5d9f1b4
Create Date: 2026-11-04 15:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "f5c8b2e6a0d3"
down_revision: Union[str, None] = "e3a7c5d9f1b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PASSES = sa.table(
    "passes",
    sa.column("has_guest", sa.Boolean()),
    sa.column("claimed_at", sa.DateTime()),
    sa.column("guest_name", sa.String()),
    sa.column("guest_waiting", sa.Boolean()),
    sa.column("guest_priority_at", sa.DateTime()),
)


def upgrade() -> None:
    with op.batch_alter_table("passes") as batch_op:
        batch_op.add_column(
            sa.Column(
                "guest_waiting", sa.Boolean(), nullable=False, server_default=sa.false()
            )
        )
        batch_op.add_column(sa.Column("guest_priority_at", sa.DateTime(), nullable=True))
    op.execute(
        PASSES.update()
        .where(PASSES.c.has_guest.is_(True))
        .values(guest_priority_at=PASSES.c.claimed_at)
    )


def downgrade() -> None:
    # Without the marker a waiting guest can't be told from no guest, so drop them.
    op.execute(
        PASSES.update().where(PASSES.c.guest_waiting.is_(True)).values(guest_name=None)
    )
    with op.batch_alter_table("passes") as batch_op:
        batch_op.drop_column("guest_priority_at")
        batch_op.drop_column("guest_waiting")
