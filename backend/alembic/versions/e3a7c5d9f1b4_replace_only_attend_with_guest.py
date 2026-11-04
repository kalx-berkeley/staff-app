"""replace only_attend_with_guest with guest_fallback

Staff will be able to choose between more than two outcomes for a +1 guest who
has no pass, so the boolean becomes a string on all three tables that store it.

Revision ID: e3a7c5d9f1b4
Revises: b4e8d1f6a2c9
Create Date: 2026-11-04 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "e3a7c5d9f1b4"
down_revision: Union[str, None] = "b4e8d1f6a2c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = ("passes", "lottery_entries", "staff_pass_alternates")


def _columns(table: str) -> sa.TableClause:
    return sa.table(
        table,
        sa.column("only_attend_with_guest", sa.Boolean()),
        sa.column("guest_fallback", sa.String()),
    )


def upgrade() -> None:
    for table in TABLES:
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "guest_fallback",
                    sa.String(),
                    nullable=False,
                    server_default="attend_alone",
                )
            )
        columns = _columns(table)
        op.execute(
            columns.update()
            .where(columns.c.only_attend_with_guest.is_(True))
            .values(guest_fallback="release")
        )
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_column("only_attend_with_guest")


def downgrade() -> None:
    # The boolean can't represent the wait options, so they become false.
    for table in TABLES:
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "only_attend_with_guest",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.false(),
                )
            )
        columns = _columns(table)
        op.execute(
            columns.update()
            .where(columns.c.guest_fallback == "release")
            .values(only_attend_with_guest=True)
        )
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_column("guest_fallback")
