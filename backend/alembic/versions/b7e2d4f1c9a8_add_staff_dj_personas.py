"""add staff dj_personas

Revision ID: b7e2d4f1c9a8
Revises: 9e4b7d2c1a63
Create Date: 2026-09-29 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "b7e2d4f1c9a8"
down_revision: Union[str, None] = "9e4b7d2c1a63"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("staff") as batch_op:
        batch_op.add_column(sa.Column("dj_personas", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("staff") as batch_op:
        batch_op.drop_column("dj_personas")
