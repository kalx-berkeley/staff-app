"""add staff instructions to shows and a default to venues

Revision ID: a4e7c2f9b1d5
Revises: d7f2b8e4a1c9
Create Date: 2026-11-12 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "a4e7c2f9b1d5"
down_revision: Union[str, None] = "d7f2b8e4a1c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("shows", sa.Column("staff_instructions", sa.Text(), nullable=True))
    op.add_column(
        "venues", sa.Column("default_staff_instructions", sa.Text(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("venues", "default_staff_instructions")
    op.drop_column("shows", "staff_instructions")
