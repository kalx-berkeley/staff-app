"""add extra_staff_passes to shows

Revision ID: 3d9b7e2c4f61
Revises: 6b1e3f8d2a57
Create Date: 2026-10-16 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "3d9b7e2c4f61"
down_revision: Union[str, None] = "6b1e3f8d2a57"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "shows",
        sa.Column(
            "extra_staff_passes",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )


def downgrade() -> None:
    op.drop_column("shows", "extra_staff_passes")
