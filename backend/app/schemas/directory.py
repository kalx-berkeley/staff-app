"""Pydantic schemas for the Staff Directory API."""

from datetime import date

from pydantic import BaseModel


class DjPersona(BaseModel):
    """One of a staff member's Spinitron DJ personas."""

    id: int
    name: str


class DirectoryEntry(BaseModel):
    """One active staff member in the Staff Directory."""

    id: int
    name: str
    pronouns: str | None = None
    email: str
    phone: str
    # Spinitron persona names joined with commas, and each persona on its own
    dj_name: str | None = None
    dj_personas: list[DjPersona] = []
    departments: list[str] = []
    statuses: list[str] = []
    titles_and_roles: str | None = None
    # Changes whenever the photo does, for cache-busting the photo URL; None
    # when the staff member has no photo.
    photo_version: str | None = None
    # Leave of absence that hasn't ended yet (None once it's past); either
    # date may be None for a one-sided leave. on_leave is True during it.
    on_leave: bool = False
    loa_start: date | None = None
    loa_end: date | None = None
