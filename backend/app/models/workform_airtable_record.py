"""WorkformAirtableRecord model — local copy of the Airtable workforms table."""

from datetime import datetime, timezone
from sqlalchemy import Column, Date, DateTime, Integer, JSON, String
from app.database import Base


class WorkformAirtableRecord(Base):
    """
    A record of the Airtable workforms table (KALX Workforms).

    Airtable is the source of truth for submitted workforms, including
    decisions made by hand there; this copy is refreshed every 15 minutes,
    after each write, and when a reviewer opens a month. Every column is
    copied from Airtable.
    """

    __tablename__ = "workform_airtable_records"

    id = Column(Integer, primary_key=True, index=True)
    airtable_record_id = Column(String, unique=True, nullable=False, index=True)
    # "Name": the linked staff record's ID (Staff.airtable_record_id)
    staff_airtable_record_id = Column(String, nullable=True, index=True)
    # "Month", normalized to the first day of the month
    month = Column(Date, nullable=True, index=True)
    # "Created Time": when the record was created, which decides lateness
    created_time = Column(DateTime, nullable=True)
    # The "<Dept> : Hours/Description/Approved" columns that have a value:
    # {department: {"hours": float | None, "description": str | None,
    # "approved": "Approved" | "Denied" | None}}
    departments = Column(JSON, nullable=False, default=dict)
    refreshed_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
