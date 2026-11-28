"""drop Spinitron's playlist automation flag

Spinitron's `automation` flag only says a playlist was created by the
station's automation system, and live DJs' playlists often are, so it can't
tell a pre-recorded slot from a live one. The pass giveaway now relies on
placeholder personas (`SPINITRON_PLACEHOLDER_PERSONA_IDS`) alone, and the
directory's Sublist DJ shift check no longer leaves out automated playlists.

Both tables are rebuilt from Spinitron on every sync, so downgrading leaves
the column false until the next one.

Revision ID: a3d7f1c9e5b8
Revises: c7a3e9d1f5b2
Create Date: 2026-11-28 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "a3d7f1c9e5b8"
down_revision: Union[str, None] = "c7a3e9d1f5b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("spinitron_playlists") as batch:
        batch.drop_column("automation")
    with op.batch_alter_table("dj_shift_playlists") as batch:
        batch.drop_column("automation")


def downgrade() -> None:
    with op.batch_alter_table("dj_shift_playlists") as batch:
        batch.add_column(
            sa.Column("automation", sa.Boolean(), nullable=False, server_default=sa.false())
        )
    with op.batch_alter_table("spinitron_playlists") as batch:
        batch.add_column(
            sa.Column("automation", sa.Boolean(), nullable=False, server_default=sa.false())
        )
