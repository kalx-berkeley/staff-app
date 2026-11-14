"""DjNameMapping model — how a DJ name typed as text maps to a persona or show."""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String

from app.database import Base


class DjNameMapping(Base):
    """
    A hand-made answer for a DJ name that can't be matched automatically.

    DJ names were typed as free text until the pass giveaway moved to
    Spinitron personas. Most match a persona or a show by name. A name that
    doesn't (a typo, a name two personas share, or a placeholder like
    "Unknown") gets one of these, made with
    `backend/scripts/spinitron_identity_report.py`. Exactly one of
    `persona_id` and `specialty_show_id` is set, or neither for a name that
    belongs to no one (the record is left unattributed).
    """

    __tablename__ = "dj_name_mappings"

    # The name normalized like `tracking_service.normalize_dj_name`
    name_key = Column(String, primary_key=True)
    persona_id = Column(Integer, nullable=True)
    specialty_show_id = Column(Integer, ForeignKey("specialty_shows.id"), nullable=True)
    # Who made the mapping, for the record
    created_by = Column(String, nullable=True)
    created_at = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
