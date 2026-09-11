"""Pydantic schemas for User API."""

from pydantic import BaseModel, Field, EmailStr, ConfigDict


class PromotionsStaffProfile(BaseModel):
    """Schema for promotions staff profile data."""

    name: str = Field(..., min_length=1, max_length=100, description="Display name")
    phone: str = Field(..., min_length=1, max_length=20, description="Contact phone number")


class StaffProfile(BaseModel):
    """Schema for staff member profile data."""

    name: str = Field(..., min_length=1, max_length=100, description="Display name")
    phone: str = Field(..., min_length=1, max_length=20, description="Contact phone number")


class PromotionsStaffResponse(BaseModel):
    """Schema for promotions staff response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    name: str
    phone: str
    dj_name: str | None = None
    is_sublist_dj: bool = False


class StaffResponse(BaseModel):
    """Schema for staff member response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    name: str
    phone: str
    dj_name: str | None = None
    is_sublist_dj: bool = False


class UserInfo(BaseModel):
    """Schema for current user information."""

    email: str | None = None
    real_email: str | None = None
    role: str  # "promotions", "staff", or "dj"
    is_dj_network: bool = False
    is_station_office_network: bool = False
    is_staging: bool = False
    impersonating_email: str | None = None
    is_impersonating_dj_network: bool = False
    is_impersonating_station_office_network: bool = False
    profile: PromotionsStaffResponse | StaffResponse | None = None


class SyncResult(BaseModel):
    """Schema for Airtable sync result."""

    promotions_upserted: list[str] = Field(
        default_factory=list, description="Promotions staff emails synced"
    )
    staff_upserted: list[str] = Field(
        default_factory=list, description="Staff member emails synced"
    )
    errors: list[str] = Field(
        default_factory=list, description="Errors encountered during sync"
    )


class NotificationPreferencesResponse(BaseModel):
    """Schema for notification preferences response."""

    model_config = ConfigDict(from_attributes=True)

    email_enabled: bool


class NotificationPreferencesUpdate(BaseModel):
    """Schema for updating notification preferences."""

    email_enabled: bool
