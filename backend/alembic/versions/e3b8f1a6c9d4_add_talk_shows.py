"""add talk & information shows

Specialty shows gain a category: "music" (Specialty Music Shows, whose
members are DJ names) or "talk" (Talk & Information shows, whose members are
staff members, kept in the new talk_show_staff table).

Revision ID: e3b8f1a6c9d4
Revises: a7d2e9c4b1f6
Create Date: 2026-11-14 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "e3b8f1a6c9d4"
down_revision: Union[str, None] = "a7d2e9c4b1f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("specialty_shows") as batch_op:
        batch_op.add_column(
            sa.Column(
                "category",
                sa.String(),
                nullable=False,
                server_default="music",
            )
        )
    op.create_table(
        "talk_show_staff",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "specialty_show_id",
            sa.Integer(),
            sa.ForeignKey("specialty_shows.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("staff_id", sa.Integer(), sa.ForeignKey("staff.id"), nullable=False),
        sa.UniqueConstraint("specialty_show_id", "staff_id"),
    )
    op.create_index("ix_talk_show_staff_staff_id", "talk_show_staff", ["staff_id"])


def downgrade() -> None:
    op.drop_index("ix_talk_show_staff_staff_id", table_name="talk_show_staff")
    op.drop_table("talk_show_staff")
    with op.batch_alter_table("specialty_shows") as batch_op:
        batch_op.drop_column("category")
