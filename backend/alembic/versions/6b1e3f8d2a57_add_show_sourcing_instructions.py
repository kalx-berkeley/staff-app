"""add show sourcing instructions to venues and promoters

Revision ID: 6b1e3f8d2a57
Revises: 92c63dc999ad
Create Date: 2026-10-13 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "6b1e3f8d2a57"
down_revision: Union[str, None] = "92c63dc999ad"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "venues", sa.Column("show_sourcing_instructions", sa.Text(), nullable=True)
    )
    op.add_column(
        "promoters", sa.Column("show_sourcing_instructions", sa.Text(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("promoters", "show_sourcing_instructions")
    op.drop_column("venues", "show_sourcing_instructions")
