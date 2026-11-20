"""add shows.tabler_open_days

How many days before a co-announce show's planned close its tabler passes open
to all Active staff, not only Publicity. Shows that aren't co-announce store it
but ignore it.

Revision ID: e8b2c4f6a1d3
Revises: a1d7e3f9c5b8
Create Date: 2026-11-20 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "e8b2c4f6a1d3"
down_revision: Union[str, None] = "a1d7e3f9c5b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("shows") as batch_op:
        batch_op.add_column(
            sa.Column(
                "tabler_open_days",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("7"),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("shows") as batch_op:
        batch_op.drop_column("tabler_open_days")
