"""add shows.num_tabler_passes

How many of a co-announce show's staff passes are set aside as tabler passes
for Publicity at the KALX Co-Announce Table. Tabler passes are pass rows with
pass_type "tabler".

Revision ID: c3a9e5d1b7f2
Revises: b4e1d7a9c2f6
Create Date: 2026-11-11 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "c3a9e5d1b7f2"
down_revision: Union[str, None] = "b4e1d7a9c2f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("shows") as batch_op:
        batch_op.add_column(
            sa.Column(
                "num_tabler_passes",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            )
        )


def downgrade() -> None:
    # Tabler passes go back to being ordinary staff passes, keeping any claims.
    op.execute("UPDATE passes SET pass_type = 'staff' WHERE pass_type = 'tabler'")
    with op.batch_alter_table("shows") as batch_op:
        batch_op.drop_column("num_tabler_passes")
