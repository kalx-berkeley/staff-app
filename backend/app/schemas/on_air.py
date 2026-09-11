"""Pydantic schemas for the on-air DJ schedule API."""

from pydantic import BaseModel

from app.schemas.types import UtcDatetime


class OnAirResponse(BaseModel):
    """Current/next on-air DJ info, derived from the cached Spinitron schedule."""

    current_dj_name: str | None = None
    current_show_ends_at: UtcDatetime | None = None
    next_dj_name: str | None = None
