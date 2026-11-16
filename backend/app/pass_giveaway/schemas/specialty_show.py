"""Pydantic schemas for the specialty show API.

Covers both kinds: Specialty Music Shows (category "music") and Talk &
Information shows (category "talk").
"""

from typing import Literal

from pydantic import BaseModel, Field, ConfigDict

SpecialtyShowCategory = Literal["music", "talk"]


class SpecialtyShowCreate(BaseModel):
    """Schema for creating a new Specialty Music Show or Talk & Info Show."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Show name (must be unique across both kinds of show)",
    )
    category: SpecialtyShowCategory = Field(
        "music",
        description=(
            "music (Specialty Music Show) or talk (Talk & Info Show); can't change later"
        ),
    )
    owner_emails: list[str] = Field(
        default_factory=list,
        description="Email addresses of staff members who own this show",
    )
    spinitron_urls: list[str] = Field(
        ...,
        min_length=1,
        description="Spinitron show or playlist links, one or more per show",
    )


class SpecialtyShowUpdate(BaseModel):
    """Schema for updating an existing Specialty Music Show or Talk & Info Show."""

    name: str | None = Field(None, min_length=1, max_length=200)
    owner_emails: list[str] | None = Field(
        None,
        description="Replace the full list of owner emails (null = no change)",
    )
    dj_persona_ids: list[int] | None = Field(
        None,
        description=(
            "Replace the full list of DJs by Spinitron persona ID (null = no"
            " change). Music shows only; each must be a current staff member's"
            " persona, or already one of the show's DJs."
        ),
    )
    staff_member_emails: list[str] | None = Field(
        None,
        description=(
            "Replace the full list of staff members by email (null = no change)."
            " Talk shows only."
        ),
    )
    spinitron_urls: list[str] | None = Field(
        None,
        description=(
            "Replace the show's Spinitron shows with these show or playlist "
            "links (null = no change). A show must have at least one."
        ),
    )


class SpecialtyShowOwnerInfo(BaseModel):
    """A specialty show owner's email and staff name, for display."""

    model_config = ConfigDict(from_attributes=True)

    email: str
    name: str | None = None


class SpecialtyShowDJInfo(BaseModel):
    """One DJ of a Specialty Music Show: a persona and its current name."""

    model_config = ConfigDict(from_attributes=True)

    persona_id: int | None = None
    name: str


class SpinitronShowInfo(BaseModel):
    """One of a specialty show's Spinitron shows."""

    id: int
    title: str | None = None
    url: str


class SpecialtyShowResponse(BaseModel):
    """Schema for specialty show response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    category: SpecialtyShowCategory = "music"
    deleted: bool = False
    retired: bool = False
    spinitron_shows: list[SpinitronShowInfo] = Field(default_factory=list)
    owner_emails: list[str] = Field(default_factory=list)
    owner_details: list[SpecialtyShowOwnerInfo] = Field(default_factory=list)
    djs: list[SpecialtyShowDJInfo] = Field(default_factory=list)
    staff_member_emails: list[str] = Field(default_factory=list)
    staff_member_details: list[SpecialtyShowOwnerInfo] = Field(default_factory=list)


class MySpecialtyShowResponse(SpecialtyShowResponse):
    """Schema for a specialty show in the current user's own list, with their role(s)."""

    is_owner: bool = False
    # A DJ member of a music show
    is_dj: bool = False
    # A staff member of a talk show
    is_staff_member: bool = False
