"""add venue default staff pass adjustment

Some venues always give more or fewer staff passes than one per pass pair.
New shows at those venues start with this Staff Pass Adjustment.

Revision ID: a7d2e9c4b1f6
Revises: c5d9a1e7f3b2
Create Date: 2026-11-13 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "a7d2e9c4b1f6"
down_revision: Union[str, None] = "c5d9a1e7f3b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("venues") as batch_op:
        batch_op.add_column(
            sa.Column(
                "default_staff_pass_adjustment",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("venues") as batch_op:
        batch_op.drop_column("default_staff_pass_adjustment")
