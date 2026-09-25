"""add staff_pass_alternates table

Revision ID: 7c3d9a2e5b1f
Revises: 5f2b6e8a1c4d
Create Date: 2026-09-25 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "7c3d9a2e5b1f"
down_revision: Union[str, None] = "5f2b6e8a1c4d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "staff_pass_alternates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("show_id", sa.Integer(), nullable=False),
        sa.Column("staff_id", sa.Integer(), nullable=False),
        sa.Column("has_guest", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("guest_name", sa.String(), nullable=True),
        sa.Column(
            "only_attend_with_guest", sa.Boolean(), server_default="false", nullable=False
        ),
        sa.Column("priority_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(), server_default="joined", nullable=False),
        sa.Column("status", sa.String(), server_default="waiting", nullable=False),
        sa.Column("promoted_pass_id", sa.Integer(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("removed_by_staff_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["show_id"], ["shows.id"]),
        sa.ForeignKeyConstraint(["staff_id"], ["staff.id"]),
        sa.ForeignKeyConstraint(["promoted_pass_id"], ["passes.id"]),
        sa.ForeignKeyConstraint(["removed_by_staff_id"], ["staff.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_staff_pass_alternates_id"), "staff_pass_alternates", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_staff_pass_alternates_show_id"),
        "staff_pass_alternates",
        ["show_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_staff_pass_alternates_staff_id"),
        "staff_pass_alternates",
        ["staff_id"],
        unique=False,
    )
    op.create_index(
        "uq_staff_pass_alternates_waiting",
        "staff_pass_alternates",
        ["show_id", "staff_id"],
        unique=True,
        sqlite_where=sa.text("status = 'waiting'"),
        postgresql_where=sa.text("status = 'waiting'"),
    )


def downgrade() -> None:
    op.drop_index("uq_staff_pass_alternates_waiting", table_name="staff_pass_alternates")
    op.drop_index(
        op.f("ix_staff_pass_alternates_staff_id"), table_name="staff_pass_alternates"
    )
    op.drop_index(
        op.f("ix_staff_pass_alternates_show_id"), table_name="staff_pass_alternates"
    )
    op.drop_index(op.f("ix_staff_pass_alternates_id"), table_name="staff_pass_alternates")
    op.drop_table("staff_pass_alternates")
