"""add venues.parent_venue_id

A venue can share another venue's win frequency limit, for venues owned by the
same company. The parent's limit covers wins at the parent and its children.

Revision ID: d7f2b8e4a1c9
Revises: c3a9e5d1b7f2
Create Date: 2026-11-12 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "d7f2b8e4a1c9"
down_revision: Union[str, None] = "c3a9e5d1b7f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("venues") as batch_op:
        batch_op.add_column(sa.Column("parent_venue_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_venues_parent_venue_id", "venues", ["parent_venue_id"], ["id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("venues") as batch_op:
        batch_op.drop_constraint("fk_venues_parent_venue_id", type_="foreignkey")
        batch_op.drop_column("parent_venue_id")
