"""Workform and WorkformEntry models — a staff member's monthly work report."""

from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from app.database import Base


class Workform(Base):
    """
    One staff member's workform for one month (KALX Workforms).

    The entries are the app's editable copy. Submitting writes the combined
    hours and descriptions to the Airtable workforms table, which is the
    source of truth from then on (see WorkformAirtableRecord). An unsubmitted
    workform is a draft and exists only here.
    """

    __tablename__ = "workforms"

    id = Column(Integer, primary_key=True, index=True)
    staff_id = Column(Integer, ForeignKey("staff.id"), nullable=False, index=True)
    # First day of the month the workform covers
    month = Column(Date, nullable=False)
    # The Airtable record the workform was submitted to; null for a draft
    airtable_record_id = Column(String, nullable=True, index=True)
    first_submitted_at = Column(DateTime, nullable=True)
    last_submitted_at = Column(DateTime, nullable=True)
    # What the last submission sent, per department:
    # {department: {"hours", "description", "entries": [{"hours", "description",
    # "work_date"}]}}. Reviewers see these entries rather than later unsent
    # edits, and a difference from Airtable's values means a hand edit there.
    submitted_blocks = Column(JSON, nullable=True)
    # The staff member's leave of absence when the workform was last submitted
    loa_start_at_submit = Column(Date, nullable=True)
    loa_end_at_submit = Column(Date, nullable=True)
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("staff_id", "month", name="uq_workform_staff_month"),
    )

    staff = relationship("Staff")
    entries = relationship(
        "WorkformEntry",
        back_populates="workform",
        cascade="all, delete-orphan",
        order_by="WorkformEntry.id",
    )


class WorkformEntry(Base):
    """One unit of work on a workform: hours in a department, and what was done."""

    __tablename__ = "workform_entries"

    id = Column(Integer, primary_key=True, index=True)
    workform_id = Column(
        Integer, ForeignKey("workforms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    department = Column(String, nullable=False)
    # A positive multiple of 0.25
    hours = Column(Float, nullable=False)
    description = Column(Text, nullable=False)
    # Optional day within the workform's month that the work was done
    work_date = Column(Date, nullable=True)
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    workform = relationship("Workform", back_populates="entries")
