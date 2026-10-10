"""Schemas for a staff member's pass giveaway notification and genre preferences."""

from pydantic import BaseModel, ConfigDict, Field


class NotificationPreferencesResponse(BaseModel):
    """Schema for notification preferences response."""

    model_config = ConfigDict(from_attributes=True)

    email_enabled: bool


class NotificationPreferencesUpdate(BaseModel):
    """Schema for updating notification preferences."""

    email_enabled: bool


class GenrePreferencesResponse(BaseModel):
    """Schema for genre preferences response."""

    model_config = ConfigDict(from_attributes=True)

    genres: list[str]


class GenrePreferencesUpdate(BaseModel):
    """Schema for updating genre preferences."""

    genres: list[str] = Field(
        default_factory=list, description="Genres the staff member likes"
    )
