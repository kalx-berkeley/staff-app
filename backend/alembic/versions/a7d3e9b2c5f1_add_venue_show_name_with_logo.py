"""add venue show_name_with_logo

Venues with a logo can show their name on the DJ view alongside the logo.
Every existing venue keeps showing the logo alone.

Revision ID: a7d3e9b2c5f1
Revises: f2a9c4d8e1b6
Create Date: 2026-10-20 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "a7d3e9b2c5f1"
down_revision: Union[str, None] = "f2a9c4d8e1b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("venues") as batch_op:
        batch_op.add_column(
            sa.Column(
                "show_name_with_logo",
                sa.Boolean(),
                nullable=False,
                server_default="false",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("venues") as batch_op:
        batch_op.drop_column("show_name_with_logo")
