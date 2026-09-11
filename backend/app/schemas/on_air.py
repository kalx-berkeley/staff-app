"""Pydantic schemas for the on-air DJ schedule API."""

from datetime import date

from pydantic import BaseModel

from app.schemas.types import UtcDatetime


class OnAirResponse(BaseModel):
    """Current/next on-air DJ info, derived from the cached Spinitron schedule."""

    current_dj_name: str | None = None
    current_show_ends_at: UtcDatetime | None = None
    next_dj_name: str | None = None


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
