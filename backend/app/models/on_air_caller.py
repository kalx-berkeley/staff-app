"""
Linked callers: on-air winners' phone numbers confirmed to be one person.

A venue's win frequency limit checks every number in the caller of the number
the DJ typed in (docs/pass-giveaway/specs/linked-callers/plan.md).
"""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class OnAirCaller(Base):
    """One person who has called in with two or more phone numbers."""

    __tablename__ = "on_air_callers"

    id = Column(Integer, primary_key=True, index=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_now, nullable=False)
    updated_at = Column(DateTime, default=_now, onupdate=_now, nullable=False)

    phones = relationship(
        "OnAirCallerPhone",
        back_populates="caller",
        cascade="all, delete-orphan",
        order_by="OnAirCallerPhone.phone",
    )


class OnAirCallerPhone(Base):
    """A phone number (as stored on `on_air_winners`) linked to a caller."""

    __tablename__ = "on_air_caller_phones"

    phone = Column(String, primary_key=True)
    caller_id = Column(
        Integer,
        ForeignKey("on_air_callers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    linked_at = Column(DateTime, default=_now, nullable=False)

    caller = relationship("OnAirCaller", back_populates="phones")


class DismissedCallerPair(Base):
    """Two phone numbers a promotions admin said belong to different people."""

    __tablename__ = "dismissed_caller_pairs"

    # phone_a < phone_b
    phone_a = Column(String, primary_key=True)
    phone_b = Column(String, primary_key=True)
    dismissed_by = Column(String, nullable=True)
    dismissed_at = Column(DateTime, default=_now, nullable=False)


class CommonCallerName(Base):
    """A normalized name too common to suggest linking its phone numbers."""

    __tablename__ = "common_caller_names"

    name = Column(String, primary_key=True)
    marked_by = Column(String, nullable=True)
    marked_at = Column(DateTime, default=_now, nullable=False)
