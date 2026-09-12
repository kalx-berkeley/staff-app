"""add spinitron_playlists table

Revision ID: d324a3e601d7
Revises: 269a20ccdde6
Create Date: 2026-09-12 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "d324a3e601d7"
down_revision: Union[str, None] = "269a20ccdde6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "spinitron_playlists",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("dj_name", sa.String(), nullable=True),
        sa.Column("persona_id", sa.Integer(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_spinitron_playlists_start"), "spinitron_playlists", ["start"], unique=False
    )
    op.create_index(
        op.f("ix_spinitron_playlists_end"), "spinitron_playlists", ["end"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_spinitron_playlists_end"), table_name="spinitron_playlists")
    op.drop_index(op.f("ix_spinitron_playlists_start"), table_name="spinitron_playlists")
    op.drop_table("spinitron_playlists")
