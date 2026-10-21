"""WorkformWorkTypes model — a department's predefined types of work."""

from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, Integer, JSON, String
from app.database import Base


class WorkformWorkTypes(Base):
    """
    The types of work a department head offers staff logging hours in their
    department (KALX Workforms).

    Keyed on the department's name rather than WorkformDepartment, because the
    staff sync rebuilds that table from Airtable. No row means no work types,
    so staff describe their work in their own words.
    """

    __tablename__ = "workform_work_types"

    id = Column(Integer, primary_key=True, index=True)
    department = Column(String, unique=True, nullable=False)
    # The work type names, in the order staff see them
    work_types = Column(JSON, nullable=False, default=list)
    # Whether staff may describe their work in their own words instead of
    # choosing a work type. Ignored while there are no work types.
    allow_free_text = Column(Boolean, nullable=False, default=True)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
