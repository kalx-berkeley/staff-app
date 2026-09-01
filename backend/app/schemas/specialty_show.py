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


class SpecialtyShowResponse(BaseModel):
    """Schema for specialty show response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    deleted: bool = False
    owner_emails: list[str] = Field(default_factory=list)
    dj_names: list[str] = Field(default_factory=list)
