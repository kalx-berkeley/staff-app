"""Pydantic schemas for the Staff Directory API."""

from pydantic import BaseModel


class DirectoryEntry(BaseModel):
    """One active staff member in the Staff Directory."""

    id: int
    name: str
    pronouns: str | None = None
    email: str
    phone: str
    # Spinitron persona names, and the persona IDs they were looked up from
    dj_name: str | None = None
    spinitron_ids: list[int] = []
    departments: list[str] = []
    statuses: list[str] = []
    titles_and_roles: str | None = None
    # Changes whenever the photo does, for cache-busting the photo URL; None
    # when the staff member has no photo.
    photo_version: str | None = None
