"""Pydantic schemas for the on-air DJ schedule API."""

from datetime import date

from typing import Literal

from pydantic import BaseModel

from app.common.schemas.types import UtcDatetime


class OnAirIdentity(BaseModel):
    """
    Who is on air: a persona, or a show (with a music show slot's DJ persona).
    """

    # "persona", or the show's category
    kind: Literal["persona", "music", "talk"]
    # The show's name, or the persona's
    name: str
    persona_id: int | None = None
    persona_name: str | None = None
    specialty_show_id: int | None = None


class OnAirResponse(BaseModel):
    """Who is on air now and next, from the Spinitron schedule and recent spins."""

    # Who giveaways are credited to now; None for no one (automation,
    # a placeholder persona, a gap, or Spinitron unavailable)
    current: OnAirIdentity | None = None
    # Whether the current slot is a Spinitron automation playlist (a
    # pre-recorded show, so there's no one live to give away passes), and
    # Spinitron's title for it, so the page can say so
    current_automation: bool = False
    current_title: str | None = None
    # When the current slot ends, so the page can look again then
    current_ends_at: UtcDatetime | None = None
    # The next slot, when its start is known
    next: OnAirIdentity | None = None
    next_starts_at: UtcDatetime | None = None
    # Whether the page may offer "I'm <next> — switch now" (the next slot is
    # someone else and starts within 10 minutes)
    can_switch_early: bool = False


class SpinMatchShow(BaseModel):
    """The show a played spin matched, lean enough for a DJ-view popup."""

    id: int
    event_name: str
    venue_name: str
    show_date: date


class SpinMatch(BaseModel):
    """A recently played spin matching a show with passes still to give away."""

    spin_id: int
    artist: str
    song: str
    image: str | None = None
    show: SpinMatchShow
