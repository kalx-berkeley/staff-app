"""Staff model."""

from datetime import datetime, timezone
from sqlalchemy import Column, Date, Integer, JSON, String, Text, DateTime
from sqlalchemy.orm import relationship
from app.database import Base


class Staff(Base):
    """
    A KALX staff member, as listed in the Airtable staff directory.

    Every column is owned by the Airtable sync (UserService.sync_from_airtable)
    and is read-only in the app; edits belong in Airtable, and a future
    self-edit feature will write through to Airtable (keyed on
    airtable_record_id) rather than change these columns directly. Data the app
    owns about a staff member lives in its own table keyed on staff_id (e.g.
    NotificationPreferences, StaffGenrePreference).

    Columns are either:
    - Airtable: copied from a field of the staff member's Airtable record
    - derived: computed during the sync from Airtable data plus another
      source, and recomputed on every sync
    """

    __tablename__ = "staff"

    id = Column(Integer, primary_key=True, index=True)
    # Airtable: the record's ID ("rec..."). Null until the first sync that
    # sees the record; the sync matches on this, falling back to email.
    airtable_record_id = Column(String, unique=True, nullable=True, index=True)
    # Airtable: "Email address"
    email = Column(String, unique=True, nullable=False, index=True)
    # Airtable: "First Name" and "Surname" as "First Last" (or "Name" as-is if
    # both are blank)
    name = Column(String, nullable=False)
    # Airtable: "Pronouns", e.g. "she/her"
    pronouns = Column(String, nullable=True)
    # Airtable: "Phone"
    phone = Column(String, nullable=False)
    # Airtable: "Titles and Roles" (free text, may span several lines)
    titles_and_roles = Column(Text, nullable=True)
    # Airtable: the ID of the "Photo" attachment whose resized copies are on
    # disk (see app/common/services/staff_photo_service.py). Null when there's no photo.
    photo_attachment_id = Column(String, nullable=True)
    # Airtable: "LOA start" and "LOA end", the first and last days (inclusive)
    # of a leave of absence. Either may be blank: a start alone is open-ended,
    # an end alone means on leave until then. See app/common/services/leave_service.py.
    loa_start = Column(Date, nullable=True)
    loa_end = Column(Date, nullable=True)
    # Derived: Spinitron persona IDs parsed from the URLs in Airtable's "DJ Name"
    spinitron_ids = Column(JSON, nullable=True)
    # Derived: persona names looked up in Spinitron for spinitron_ids
    dj_name = Column(String, nullable=True)
    # Derived: the same lookup as [{"id": persona_id, "name": persona_name}],
    # keeping each name with its persona (dj_name joins them with commas)
    dj_personas = Column(JSON, nullable=True)
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    claimed_passes = relationship(
        "Pass", foreign_keys="[Pass.staff_id]", back_populates="staff"
    )
    # Airtable: "Department"
    departments = relationship(
        "StaffDepartment", back_populates="staff", cascade="all, delete-orphan"
    )
    # Airtable: "Status"
    statuses = relationship(
        "StaffStatus", back_populates="staff", cascade="all, delete-orphan"
    )
