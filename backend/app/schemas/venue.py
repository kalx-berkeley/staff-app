"""Pydantic schemas for Venue API."""

from pydantic import BaseModel, Field, ConfigDict
from app.schemas.promoter import PromoterResponse


class VenueContactCreate(BaseModel):
    name: str | None = None
    title: str | None = None
    email: str | None = None
    phone: str | None = None


class VenueContactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str | None = None
    title: str | None = None
    email: str | None = None
    phone: str | None = None


class VenueCreate(BaseModel):
    """Schema for creating a new venue."""

    name: str = Field(
        ..., min_length=1, max_length=200, description="Venue name (must be unique)"
    )
    address: str = Field(
        ..., min_length=1, max_length=500, description="Venue postal address"
    )
    pass_call_instructions: str | None = None
    win_frequency_days: int | None = None
    default_wheelchair_accessible: bool | None = None
    default_age_restriction: str | None = None
    default_num_pass_pairs: int | None = None
    requires_phone_number: bool = False
    requires_email_address: bool = False
    staff_guest_requires_name: bool = False
    default_lottery_enabled: bool = False
    default_lottery_window_hours: int = 24
    default_dj_preassign_prohibition_days: int | None = None
    default_close_hours_before_show: int | None = None
    promoter_id: int | None = Field(
        None, description="Default promoter for shows at this venue"
    )
    shows_have_external_promoter: bool = False
    owner_emails: list[str] = Field(default_factory=list)
    contacts: list[VenueContactCreate] = Field(default_factory=list)


class VenueUpdate(BaseModel):
    """Schema for updating an existing venue."""

    name: str | None = Field(None, min_length=1, max_length=200)
    address: str | None = Field(None, min_length=1, max_length=500)
    pass_call_instructions: str | None = None
    win_frequency_days: int | None = None
    default_wheelchair_accessible: bool | None = None
    default_age_restriction: str | None = None
    default_num_pass_pairs: int | None = None
    requires_phone_number: bool | None = None
    requires_email_address: bool | None = None
    staff_guest_requires_name: bool | None = None
    default_lottery_enabled: bool | None = None
    default_lottery_window_hours: int | None = None
    default_dj_preassign_prohibition_days: int | None = None
    default_close_hours_before_show: int | None = None
    promoter_id: int | None = None
    shows_have_external_promoter: bool | None = None
    owner_emails: list[str] | None = None
    contacts: list[VenueContactCreate] | None = None


class VenueResponse(BaseModel):
    """Schema for venue response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    address: str
    pass_call_instructions: str | None = None
    win_frequency_days: int | None = None
    default_wheelchair_accessible: bool | None = None
    default_age_restriction: str | None = None
    default_num_pass_pairs: int | None = None
    requires_phone_number: bool = False
    requires_email_address: bool = False
    staff_guest_requires_name: bool = False
    default_lottery_enabled: bool = False
    default_lottery_window_hours: int = 24
    default_dj_preassign_prohibition_days: int | None = None
    default_close_hours_before_show: int | None = None
    has_logo: bool = False
    deleted: bool = False
    promoter_id: int | None = None
    promoter: PromoterResponse | None = None
    shows_have_external_promoter: bool = False
    owner_emails: list[str] = Field(default_factory=list)
    contacts: list[VenueContactResponse] = Field(default_factory=list)

    @classmethod
    def from_orm_venue(cls, venue):
        return cls(
            id=venue.id,
            name=venue.name,
            address=venue.address,
            pass_call_instructions=venue.pass_call_instructions,
            win_frequency_days=venue.win_frequency_days,
            default_wheelchair_accessible=venue.default_wheelchair_accessible,
            default_age_restriction=venue.default_age_restriction,
            default_num_pass_pairs=venue.default_num_pass_pairs,
            requires_phone_number=venue.requires_phone_number,
            requires_email_address=venue.requires_email_address,
            staff_guest_requires_name=venue.staff_guest_requires_name,
            default_lottery_enabled=venue.default_lottery_enabled,
            default_lottery_window_hours=venue.default_lottery_window_hours,
            default_dj_preassign_prohibition_days=venue.default_dj_preassign_prohibition_days,
            default_close_hours_before_show=venue.default_close_hours_before_show,
            has_logo=bool(venue.logo_filename),
            promoter_id=venue.promoter_id,
            promoter=(
                PromoterResponse.from_orm_promoter(venue.promoter)
                if venue.promoter
                else None
            ),
            shows_have_external_promoter=venue.shows_have_external_promoter,
            owner_emails=[o.promotions_staff_email for o in venue.owners],
            contacts=[VenueContactResponse.model_validate(c) for c in venue.contacts],
        )
