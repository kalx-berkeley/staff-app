"""add hold_close_notifications and the show state that goes with it

Venues and promoters can choose to hold the emails telling staff and alternates
the outcome when a show closes, until a promotions rep clicks a button on the
show page. Shows record whether their emails are held, when and by whom they
were sent, and when the show was last reopened (so a restart doesn't auto-close
a show a rep reopened after its planned close time).

Revision ID: b4e8d1f6a2c9
Revises: a7d3e9c1f5b8
Create Date: 2026-11-04 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "b4e8d1f6a2c9"
down_revision: Union[str, None] = "a7d3e9c1f5b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = ("venues", "promoters")


def upgrade() -> None:
    for table in TABLES:
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "hold_close_notifications",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.false(),
                )
            )
    with op.batch_alter_table("shows") as batch_op:
        batch_op.add_column(
            sa.Column(
                "close_notifications_held",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch_op.add_column(
            sa.Column(
                "close_notifications_sent_at", sa.DateTime(timezone=True), nullable=True
            )
        )
        batch_op.add_column(
            sa.Column("close_notifications_sent_by", sa.String(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("reopened_at", sa.DateTime(timezone=True), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("shows") as batch_op:
        batch_op.drop_column("reopened_at")
        batch_op.drop_column("close_notifications_sent_by")
        batch_op.drop_column("close_notifications_sent_at")
        batch_op.drop_column("close_notifications_held")
    for table in TABLES:
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_column("hold_close_notifications")
