"""add default on-air description and caller special instructions to venues

Revision ID: 8d4a1e6c3b72
Revises: 3d9b7e2c4f61
Create Date: 2026-10-16 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "8d4a1e6c3b72"
down_revision: Union[str, None] = "3d9b7e2c4f61"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "venues", sa.Column("default_on_air_description", sa.Text(), nullable=True)
    )
    op.add_column(
        "venues",
        sa.Column("default_caller_special_instructions", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("venues", "default_caller_special_instructions")
    op.drop_column("venues", "default_on_air_description")
