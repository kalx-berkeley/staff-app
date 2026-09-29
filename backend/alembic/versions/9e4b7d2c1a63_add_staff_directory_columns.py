"""add staff directory columns

Revision ID: 9e4b7d2c1a63
Revises: 7c3d9a2e5b1f
Create Date: 2026-09-29 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "9e4b7d2c1a63"
down_revision: Union[str, None] = "7c3d9a2e5b1f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("staff") as batch_op:
        batch_op.add_column(sa.Column("airtable_record_id", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("pronouns", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("titles_and_roles", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("photo_attachment_id", sa.String(), nullable=True))
        batch_op.create_index(
            batch_op.f("ix_staff_airtable_record_id"), ["airtable_record_id"], unique=True
        )


def downgrade() -> None:
    with op.batch_alter_table("staff") as batch_op:
        batch_op.drop_index(batch_op.f("ix_staff_airtable_record_id"))
        batch_op.drop_column("photo_attachment_id")
        batch_op.drop_column("titles_and_roles")
        batch_op.drop_column("pronouns")
        batch_op.drop_column("airtable_record_id")
