"""add area to audit_log

Each audit log entry records which part of the app it belongs to, so that
promotions admins can be shown only the pass giveaway's entries.

Revision ID: 5a8c2e9f4b17
Revises: 8d4a1e6c3b72
Create Date: 2026-10-17 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "5a8c2e9f4b17"
down_revision: Union[str, None] = "8d4a1e6c3b72"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("audit_log", sa.Column("area", sa.String(), nullable=True))
    # Existing entries get their area from their event type. Emails were sent
    # by every sub-site and can't be told apart, so they count as Common,
    # which hides them from promotions admins. Everything else that isn't the
    # staff sync or workforms is from the pass giveaway, which the audit log
    # was first written for.
    op.execute(
        "UPDATE audit_log SET area = CASE"
        " WHEN event_type = 'email_sent' OR event_type LIKE 'airtable_sync_%'"
        " THEN 'Common'"
        " WHEN event_type LIKE 'workform_%' THEN 'KALX Workforms'"
        " ELSE 'Radio Pass Giveaway' END"
    )
    with op.batch_alter_table("audit_log") as batch_op:
        batch_op.alter_column("area", existing_type=sa.String(), nullable=False)
        batch_op.create_index("ix_audit_log_area", ["area"])


def downgrade() -> None:
    with op.batch_alter_table("audit_log") as batch_op:
        batch_op.drop_index("ix_audit_log_area")
        batch_op.drop_column("area")
