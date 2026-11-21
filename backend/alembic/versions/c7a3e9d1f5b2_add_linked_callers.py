"""add linked callers

On-air winners' phone numbers confirmed to be one caller, so a venue's win
frequency limit checks all of them, plus dismissed suggestions and names too
common to suggest (docs/pass-giveaway/specs/linked-callers/plan.md).

Revision ID: c7a3e9d1f5b2
Revises: b4d1e7a9c2f6
Create Date: 2026-11-21 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "c7a3e9d1f5b2"
down_revision: Union[str, None] = "b4d1e7a9c2f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "on_air_callers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_on_air_callers_id", "on_air_callers", ["id"])
    op.create_table(
        "on_air_caller_phones",
        sa.Column("phone", sa.String(), primary_key=True),
        sa.Column(
            "caller_id",
            sa.Integer(),
            sa.ForeignKey("on_air_callers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("linked_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_on_air_caller_phones_caller_id", "on_air_caller_phones", ["caller_id"]
    )
    op.create_table(
        "dismissed_caller_pairs",
        sa.Column("phone_a", sa.String(), primary_key=True),
        sa.Column("phone_b", sa.String(), primary_key=True),
        sa.Column("dismissed_by", sa.String(), nullable=True),
        sa.Column("dismissed_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "common_caller_names",
        sa.Column("name", sa.String(), primary_key=True),
        sa.Column("marked_by", sa.String(), nullable=True),
        sa.Column("marked_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("common_caller_names")
    op.drop_table("dismissed_caller_pairs")
    op.drop_index("ix_on_air_caller_phones_caller_id", "on_air_caller_phones")
    op.drop_table("on_air_caller_phones")
    op.drop_index("ix_on_air_callers_id", "on_air_callers")
    op.drop_table("on_air_callers")
