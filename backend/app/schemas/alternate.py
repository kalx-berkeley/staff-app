"""Pydantic schemas for the staff-pass alternate queue API."""

from datetime import date
from pydantic import BaseModel, ConfigDict
from app.schemas.types import UtcDatetime


class AlternateJoinRequest(BaseModel):
    """Body for joining a show's alternate queue (same shape as a claim)."""

    has_guest: bool = False
    guest_name: str | None = None
    only_attend_with_guest: bool = False


class AlternateUpdateRequest(AlternateJoinRequest):
    """Body for changing an alternate entry's +1 details."""


class AlternateEntryResponse(BaseModel):
    """One waiting entry in a show's alternate queue."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    show_id: int
    staff_id: int
    staff_name: str | None = None
    position: int
    has_guest: bool
    guest_name: str | None
    only_attend_with_guest: bool
    source: str
    priority_at: UtcDatetime


class AlternateQueueResponse(BaseModel):
    """A show's alternate queue as seen by the current user."""

    queue_open: bool
    entries: list[AlternateEntryResponse]
    my_entry_id: int | None = None
    # Who would get the current user's pass if they released it now.
    next_candidate_staff_id: int | None = None
    next_candidate_name: str | None = None


class MyAlternateEntryResponse(AlternateEntryResponse):
    """One of the current user's waiting entries, with show details."""

    show_event_name: str | None = None
    show_date: date | None = None
    show_venue_name: str | None = None
