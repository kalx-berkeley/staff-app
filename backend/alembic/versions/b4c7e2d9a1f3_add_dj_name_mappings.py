"""add dj name mappings

Hand-made answers for DJ names typed as text that don't match a Spinitron
persona or a show by name, made with scripts/spinitron_identity_report.py
ahead of the move to Spinitron personas.

Revision ID: b4c7e2d9a1f3
Revises: e3b8f1a6c9d4
Create Date: 2026-11-14 18:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "b4c7e2d9a1f3"
down_revision: Union[str, None] = "e3b8f1a6c9d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "dj_name_mappings",
        sa.Column("name_key", sa.String(), primary_key=True),
        sa.Column("persona_id", sa.Integer(), nullable=True),
        sa.Column(
            "specialty_show_id",
            sa.Integer(),
            sa.ForeignKey("specialty_shows.id"),
            nullable=True,
        ),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("dj_name_mappings")
