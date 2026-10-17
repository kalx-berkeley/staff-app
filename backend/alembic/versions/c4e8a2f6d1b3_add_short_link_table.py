"""add short_link table

Revision ID: c4e8a2f6d1b3
Revises: 5a8c2e9f4b17
Create Date: 2026-10-17 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "c4e8a2f6d1b3"
down_revision: Union[str, None] = "5a8c2e9f4b17"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "short_link",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("target_url", sa.String(length=2048), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by_email", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_short_link_id"), "short_link", ["id"], unique=False)
    op.create_index(op.f("ix_short_link_slug"), "short_link", ["slug"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_short_link_slug"), table_name="short_link")
    op.drop_index(op.f("ix_short_link_id"), table_name="short_link")
    op.drop_table("short_link")
