"""allow unknown wheelchair accessibility

Shows' wheelchair_accessible and venues' default_wheelchair_accessible change
from booleans to "yes", "no" or "unknown". A venue's default stays nullable,
where null means no default.

Revision ID: e8b3f5a2c7d4
Revises: c4e8a2f6d1b3
Create Date: 2026-10-19 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "e8b3f5a2c7d4"
down_revision: Union[str, None] = "c4e8a2f6d1b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TO_STRING = "CASE WHEN {col} THEN 'yes' WHEN NOT {col} THEN 'no' END"
TO_BOOLEAN = "CASE {col} WHEN 'yes' THEN 1 WHEN 'no' THEN 0 END"


def _convert(table, column, new_type, expression, nullable, unknown_as=None):
    """Replace a column with one of a new type, filled in by expression."""
    temp = f"{column}_new"
    op.add_column(table, sa.Column(temp, new_type, nullable=True))
    op.execute(f"UPDATE {table} SET {temp} = {expression.format(col=column)}")
    if unknown_as is not None:
        op.execute(f"UPDATE {table} SET {temp} = {unknown_as} WHERE {temp} IS NULL")
    with op.batch_alter_table(table) as batch_op:
        batch_op.drop_column(column)
        batch_op.alter_column(
            temp, new_column_name=column, existing_type=new_type, nullable=nullable
        )


def upgrade() -> None:
    _convert("shows", "wheelchair_accessible", sa.String(), TO_STRING, False, "'unknown'")
    _convert("venues", "default_wheelchair_accessible", sa.String(), TO_STRING, True)


def downgrade() -> None:
    # Unknown has no boolean equivalent. Shows fall back to accessible, the
    # old default for new shows, and venues to no default.
    _convert("shows", "wheelchair_accessible", sa.Boolean(), TO_BOOLEAN, False, "1")
    _convert("venues", "default_wheelchair_accessible", sa.Boolean(), TO_BOOLEAN, True)
