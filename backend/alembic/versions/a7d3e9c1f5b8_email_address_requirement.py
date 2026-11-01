"""replace requires_email_address with email_address_requirement

Venues and promoters choose which winners' email addresses the guest list
needs: "none", "staff_passes" (staff claimants only) or "all" (DJs also
collect one from every on-air winner). requires_email_address becomes "all".

Revision ID: a7d3e9c1f5b8
Revises: c9f1a3e5b7d2
Create Date: 2026-11-01 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "a7d3e9c1f5b8"
down_revision: Union[str, None] = "c9f1a3e5b7d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = ("venues", "promoters")


def upgrade() -> None:
    for table in TABLES:
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "email_address_requirement",
                    sa.String(),
                    nullable=False,
                    server_default="none",
                )
            )
        op.execute(
            f"UPDATE {table} SET email_address_requirement = 'all'"
            " WHERE requires_email_address"
        )
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_column("requires_email_address")


def downgrade() -> None:
    # "staff_passes" has no equivalent and becomes false: staff claimants'
    # addresses are then left out of the guest list.
    for table in TABLES:
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "requires_email_address",
                    sa.Boolean(),
                    nullable=False,
                    server_default="false",
                )
            )
        op.execute(
            f"UPDATE {table} SET requires_email_address = true"
            " WHERE email_address_requirement = 'all'"
        )
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_column("email_address_requirement")
