"""add staff leave of absence

Revision ID: 4f8a2c6e1b9d
Revises: b7e2d4f1c9a8
Create Date: 2026-10-04 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "4f8a2c6e1b9d"
down_revision: Union[str, None] = "b7e2d4f1c9a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("staff") as batch_op:
        batch_op.add_column(sa.Column("loa_start", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("loa_end", sa.Date(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("staff") as batch_op:
        batch_op.drop_column("loa_end")
        batch_op.drop_column("loa_start")
