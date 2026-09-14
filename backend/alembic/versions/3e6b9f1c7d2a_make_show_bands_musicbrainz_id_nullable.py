"""make show_bands.musicbrainz_id nullable

Revision ID: 3e6b9f1c7d2a
Revises: a1f3c9d0e7b2
Create Date: 2026-09-14 22:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "3e6b9f1c7d2a"
down_revision: Union[str, None] = "a1f3c9d0e7b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("show_bands") as batch_op:
        batch_op.alter_column("musicbrainz_id", existing_type=sa.String(), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("show_bands") as batch_op:
        batch_op.alter_column("musicbrainz_id", existing_type=sa.String(), nullable=False)
