"""Pydantic schemas for the staff-pass alternate queue API."""

from datetime import date
from pydantic import BaseModel, ConfigDict
from app.common.schemas.types import UtcDatetime
from app.models.guest_fallback import GuestFallback
from app.pass_giveaway.schemas.guest_fallback import GuestFallbackChoice


class AlternateJoinRequest(BaseModel):
    """Body for joining a show's alternate queue (same shape as a claim)."""

    has_guest: bool = False
    guest_name: str | None = None
    guest_fallback: GuestFallbackChoice = GuestFallback.ATTEND_ALONE


class AlternateUpdateRequest(AlternateJoinRequest):
    """Body for changing an alternate entry's +1 details."""


class AlternateEntryResponse(BaseModel):
    """One waiting entry in a show's alternate queue."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    show_id: int
    staff_id: int
    staff_name: str | None = None
    # Only filled in for promotions staff viewing the queue.
    staff_phone: str | None = None
    staff_email: str | None = None
    position: int
    has_guest: bool
    guest_name: str | None
    guest_fallback: str
    source: str
    priority_at: UtcDatetime


class WaitingGuestResponse(BaseModel):
    """A staff member's +1 guest waiting on the alternate list."""

    pass_id: int
    position: int
    guest_name: str | None = None
    host_staff_id: int | None = None
    host_name: str | None = None
    is_mine: bool = False


class AlternateQueueResponse(BaseModel):
    """A show's alternate queue as seen by the current user."""

    queue_open: bool
    entries: list[AlternateEntryResponse]
    waiting_guests: list[WaitingGuestResponse] = []
    my_entry_id: int | None = None
    # Who would get the current user's pass if they released it now.
    next_candidate_staff_id: int | None = None
    next_candidate_name: str | None = None
    # The current user was on the list when the show closed, and the email telling
    # them the outcome is being held.
    my_outcome_pending: bool = False


class MyAlternateEntryResponse(AlternateEntryResponse):
    """One of the current user's waiting or outcome-pending entries, with show details."""

    outcome_pending: bool = False
    show_event_name: str | None = None
    show_date: date | None = None
    show_venue_name: str | None = None
