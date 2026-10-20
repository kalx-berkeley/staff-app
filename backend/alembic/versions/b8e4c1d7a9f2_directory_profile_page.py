"""directory profile page

Adds what the Staff Directory's profile page needs: the staff table's First
Name, Surname and DJ Quiz values from Airtable, the DJ Quiz deadlines (seeded
with 2025 and 2026), the playlists the Sublist DJ shift requirement checks,
and Spinitron show IDs and a retired state for specialty shows.

Revision ID: b8e4c1d7a9f2
Revises: a7d3e9b2c5f1
Create Date: 2026-10-20 12:00:00.000000

"""

from datetime import date, datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "b8e4c1d7a9f2"
down_revision: Union[str, None] = "a7d3e9b2c5f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("staff") as batch_op:
        batch_op.add_column(sa.Column("first_name", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("surname", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("dj_quiz_years", sa.JSON(), nullable=True))

    deadlines = op.create_table(
        "dj_quiz_deadlines",
        sa.Column("year", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("deadline", sa.Date(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("year"),
    )
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    op.bulk_insert(
        deadlines,
        [
            {"year": 2025, "deadline": date(2025, 7, 31), "updated_at": now},
            {"year": 2026, "deadline": date(2026, 9, 30), "updated_at": now},
        ],
    )

    op.create_table(
        "dj_shift_playlists",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("persona_id", sa.Integer(), nullable=True),
        sa.Column("show_id", sa.Integer(), nullable=True),
        sa.Column("start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("automation", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_dj_shift_playlists_persona_id", "dj_shift_playlists", ["persona_id"]
    )
    op.create_index("ix_dj_shift_playlists_start", "dj_shift_playlists", ["start"])

    op.create_table(
        "specialty_show_spinitron_shows",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("specialty_show_id", sa.Integer(), nullable=False),
        sa.Column("spinitron_show_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(
            ["specialty_show_id"], ["specialty_shows.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("spinitron_show_id"),
    )
    op.create_index(
        "ix_specialty_show_spinitron_shows_id",
        "specialty_show_spinitron_shows",
        ["id"],
    )

    with op.batch_alter_table("specialty_shows") as batch_op:
        batch_op.add_column(sa.Column("retired_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("specialty_shows") as batch_op:
        batch_op.drop_column("retired_at")
    op.drop_index(
        "ix_specialty_show_spinitron_shows_id",
        table_name="specialty_show_spinitron_shows",
    )
    op.drop_table("specialty_show_spinitron_shows")
    op.drop_index("ix_dj_shift_playlists_start", table_name="dj_shift_playlists")
    op.drop_index("ix_dj_shift_playlists_persona_id", table_name="dj_shift_playlists")
    op.drop_table("dj_shift_playlists")
    op.drop_table("dj_quiz_deadlines")
    with op.batch_alter_table("staff") as batch_op:
        batch_op.drop_column("dj_quiz_years")
        batch_op.drop_column("surname")
        batch_op.drop_column("first_name")
