"""add venue type and movie rating

Venues get a venue_type, "music" (every existing venue) or "movie_theater",
and a default_movie_rating. Shows at a movie theater have a movie_rating
instead of an age_restriction, so shows' age_restriction becomes nullable.

Revision ID: f2a9c4d8e1b6
Revises: e8b3f5a2c7d4
Create Date: 2026-10-19 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "f2a9c4d8e1b6"
down_revision: Union[str, None] = "e8b3f5a2c7d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("venues") as batch_op:
        batch_op.add_column(
            sa.Column("venue_type", sa.String(), nullable=False, server_default="music")
        )
        batch_op.add_column(sa.Column("default_movie_rating", sa.String(), nullable=True))
    with op.batch_alter_table("shows") as batch_op:
        batch_op.add_column(sa.Column("movie_rating", sa.String(), nullable=True))
        batch_op.alter_column("age_restriction", existing_type=sa.String(), nullable=True)


def downgrade() -> None:
    # Movie theater shows have no age restriction. Fall back to all ages, the
    # default for new shows.
    op.execute(
        "UPDATE shows SET age_restriction = 'all_ages' WHERE age_restriction IS NULL"
    )
    with op.batch_alter_table("shows") as batch_op:
        batch_op.alter_column("age_restriction", existing_type=sa.String(), nullable=False)
        batch_op.drop_column("movie_rating")
    with op.batch_alter_table("venues") as batch_op:
        batch_op.drop_column("default_movie_rating")
        batch_op.drop_column("venue_type")
