"""Pydantic schemas for the Staff Directory API."""

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
