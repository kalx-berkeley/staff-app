"""add the columns the schedule cache needs to tell who is on air

Phase 3 of docs/pass-giveaway/specs/spinitron-identity/plan.md. The cached
schedule (`spinitron_playlists`, `spinitron_shows`) stored only the first
persona and a resolved DJ name. Telling a Specialty Music Show or Talk & Info
Show slot apart needs each playlist's Spinitron show ID (decision 5), and
telling a slot with no DJ apart needs the title (FREEFORM and other non-DJ
titles) and, for playlists, Spinitron's automation flag (decision 21).

The cache is rebuilt from Spinitron on every sync, so existing rows are left
empty until the next one.

Revision ID: d6f2b8e4a0c1
Revises: c5e1a7d3f9b2
Create Date: 2026-11-16 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "d6f2b8e4a0c1"
down_revision: Union[str, None] = "c5e1a7d3f9b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("spinitron_playlists") as batch:
        batch.add_column(sa.Column("show_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("title", sa.String(), nullable=True))
        batch.add_column(
            sa.Column("automation", sa.Boolean(), nullable=False, server_default=sa.false())
        )
    with op.batch_alter_table("spinitron_shows") as batch:
        batch.add_column(sa.Column("title", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("spinitron_shows") as batch:
        batch.drop_column("title")
    with op.batch_alter_table("spinitron_playlists") as batch:
        batch.drop_column("automation")
        batch.drop_column("title")
        batch.drop_column("show_id")
