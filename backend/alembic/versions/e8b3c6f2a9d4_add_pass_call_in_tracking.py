"""add pass call-in tracking

Venues and promoters can opt in to tracking when a promotions rep has called
in a closed show's passes, recorded on the show.

Revision ID: e8b3c6f2a9d4
Revises: a4e7c2f9b1d5
Create Date: 2026-11-12 18:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "e8b3c6f2a9d4"
down_revision: Union[str, None] = "a4e7c2f9b1d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for table in ("venues", "promoters"):
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "track_pass_call_in",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.false(),
                )
            )
    with op.batch_alter_table("shows") as batch_op:
        batch_op.add_column(
            sa.Column("passes_called_in_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(sa.Column("passes_called_in_by", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("shows") as batch_op:
        batch_op.drop_column("passes_called_in_by")
        batch_op.drop_column("passes_called_in_at")
    for table in ("promoters", "venues"):
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_column("track_pass_call_in")
