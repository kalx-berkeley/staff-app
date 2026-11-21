"""add staff.birth_year

The year a staff member was born, from the Airtable staff table's "Birth year"
field, used to keep staff who are under 21 from getting passes to 21+ shows.

Revision ID: b4d1e7a9c2f6
Revises: e8b2c4f6a1d3
Create Date: 2026-11-20 14:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "b4d1e7a9c2f6"
down_revision: Union[str, None] = "e8b2c4f6a1d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("staff") as batch_op:
        batch_op.add_column(sa.Column("birth_year", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("staff") as batch_op:
        batch_op.drop_column("birth_year")
