"""Pydantic schemas for SpecialtyShow API."""

from pydantic import BaseModel, Field, ConfigDict


class SpecialtyShowCreate(BaseModel):
    """Schema for creating a new specialty show."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Specialty show name (must be unique)",
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
    """Schema for updating an existing specialty show."""

    name: str | None = Field(None, min_length=1, max_length=200)
    owner_emails: list[str] | None = Field(
        None,
        description="Replace the full list of owner emails (null = no change)",
    )
    dj_names: list[str] | None = Field(
        None,
        description="Replace the full list of DJ names (null = no change)",
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
    deleted: bool = False
    retired: bool = False
    spinitron_shows: list[SpinitronShowInfo] = Field(default_factory=list)
    owner_emails: list[str] = Field(default_factory=list)
    owner_details: list[SpecialtyShowOwnerInfo] = Field(default_factory=list)
    dj_names: list[str] = Field(default_factory=list)


class MySpecialtyShowResponse(SpecialtyShowResponse):
    """Schema for a specialty show in the current user's own list, with their role(s)."""

    is_owner: bool = False
    is_dj: bool = False
