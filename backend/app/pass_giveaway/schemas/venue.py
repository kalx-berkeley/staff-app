"""Pydantic schemas for Venue API."""

from typing import Literal

from pydantic import BaseModel, Field, ConfigDict
from app.models.venue import venue_sort_key
from app.pass_giveaway.schemas.promoter import EmailAddressRequirement, PromoterResponse

# Whether a show's venue is wheelchair accessible, "unknown" when nobody has
# found out
WheelchairAccessible = Literal["yes", "no", "unknown"]

# Shows at a movie theater have a movie rating instead of an age restriction
VenueType = Literal["music", "movie_theater"]
AgeRestriction = Literal["all_ages", "18+", "21+"]
# "NR" is Not Rated
MovieRating = Literal["G", "PG", "PG-13", "R", "NC-17", "NR"]


class VenueContactCreate(BaseModel):
    name: str | None = None
    title: str | None = None
    email: str | None = None
    phone: str | None = None


class VenueOwnerInfo(BaseModel):
    """A KALX promotions rep who owns the venue, for display."""

    email: str
    name: str | None = None


class VenueContactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str | None = None
    title: str | None = None
    email: str | None = None
    phone: str | None = None


class VenueRef(BaseModel):
    """Another venue, by ID and name."""

    id: int
    name: str


class VenueCreate(BaseModel):
    """Schema for creating a new venue."""

    name: str = Field(
        ..., min_length=1, max_length=200, description="Venue name (must be unique)"
    )
    address: str = Field(
        ..., min_length=1, max_length=500, description="Venue postal address"
    )
    show_sourcing_instructions: str | None = None
    pass_call_instructions: str | None = None
    win_frequency_days: int | None = None
    # Share this venue's win frequency limit with (be a child of) another venue
    parent_venue_id: int | None = None
    venue_type: VenueType = "music"
    default_wheelchair_accessible: WheelchairAccessible | None = None
    default_age_restriction: str | None = None
    default_movie_rating: MovieRating | None = None
    default_num_pass_pairs: int | None = None
    requires_phone_number: bool = False
    email_address_requirement: EmailAddressRequirement = "none"
    staff_guest_requires_name: bool = False
    hold_close_notifications: bool = False
    track_pass_call_in: bool = False
    default_lottery_enabled: bool = False
    default_lottery_window_hours: int = 24
    default_dj_preassign_prohibition_days: int | None = None
    default_close_hours_before_show: int | None = None
    default_on_air_description: str | None = Field(None, max_length=2000)
    default_caller_special_instructions: str | None = Field(None, max_length=1000)
    default_staff_instructions: str | None = Field(None, max_length=2000)
    promoter_id: int | None = Field(
        None, description="Default promoter for shows at this venue"
    )
    shows_have_external_promoter: bool = False
    show_name_with_logo: bool = False
    owner_emails: list[str] = Field(default_factory=list)
    contacts: list[VenueContactCreate] = Field(default_factory=list)


class VenueUpdate(BaseModel):
    """Schema for updating an existing venue."""

    name: str | None = Field(None, min_length=1, max_length=200)
    address: str | None = Field(None, min_length=1, max_length=500)
    show_sourcing_instructions: str | None = None
    pass_call_instructions: str | None = None
    win_frequency_days: int | None = None
    parent_venue_id: int | None = None
    venue_type: VenueType | None = None
    default_wheelchair_accessible: WheelchairAccessible | None = None
    default_age_restriction: str | None = None
    default_movie_rating: MovieRating | None = None
    default_num_pass_pairs: int | None = None
    requires_phone_number: bool | None = None
    email_address_requirement: EmailAddressRequirement | None = None
    staff_guest_requires_name: bool | None = None
    hold_close_notifications: bool | None = None
    track_pass_call_in: bool | None = None
    default_lottery_enabled: bool | None = None
    default_lottery_window_hours: int | None = None
    default_dj_preassign_prohibition_days: int | None = None
    default_close_hours_before_show: int | None = None
    default_on_air_description: str | None = Field(None, max_length=2000)
    default_caller_special_instructions: str | None = Field(None, max_length=1000)
    default_staff_instructions: str | None = Field(None, max_length=2000)
    promoter_id: int | None = None
    shows_have_external_promoter: bool | None = None
    show_name_with_logo: bool | None = None
    owner_emails: list[str] | None = None
    contacts: list[VenueContactCreate] | None = None


class VenueResponse(BaseModel):
    """Schema for venue response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    address: str
    show_sourcing_instructions: str | None = None
    pass_call_instructions: str | None = None
    win_frequency_days: int | None = None
    # The venue whose limit this venue shares, if any
    parent_venue_id: int | None = None
    parent_venue_name: str | None = None
    # The venues that share this venue's limit
    children: list[VenueRef] = Field(default_factory=list)
    # The limit that applies to this venue's shows: the parent's, or its own
    effective_win_frequency_days: int | None = None
    # The other venues that limit applies to, when there is a limit
    win_frequency_shared_with: list[str] = Field(default_factory=list)
    venue_type: VenueType = "music"
    default_wheelchair_accessible: WheelchairAccessible | None = None
    default_age_restriction: str | None = None
    default_movie_rating: MovieRating | None = None
    default_num_pass_pairs: int | None = None
    requires_phone_number: bool = False
    email_address_requirement: EmailAddressRequirement = "none"
    # Derived from email_address_requirement: DJs must collect on-air winners' emails
    requires_email_address: bool = False
    staff_guest_requires_name: bool = False
    hold_close_notifications: bool = False
    track_pass_call_in: bool = False
    default_lottery_enabled: bool = False
    default_lottery_window_hours: int = 24
    default_dj_preassign_prohibition_days: int | None = None
    default_close_hours_before_show: int | None = None
    default_on_air_description: str | None = None
    default_caller_special_instructions: str | None = None
    default_staff_instructions: str | None = None
    has_logo: bool = False
    show_name_with_logo: bool = False
    deleted: bool = False
    promoter_id: int | None = None
    promoter: PromoterResponse | None = None
    shows_have_external_promoter: bool = False
    owner_emails: list[str] = Field(default_factory=list)
    # The owners are the venue's KALX promotions reps
    owner_details: list[VenueOwnerInfo] = Field(default_factory=list)
    contacts: list[VenueContactResponse] = Field(default_factory=list)

    @classmethod
    def from_orm_venue(cls, venue):
        return cls(
            id=venue.id,
            name=venue.name,
            address=venue.address,
            show_sourcing_instructions=venue.show_sourcing_instructions,
            pass_call_instructions=venue.pass_call_instructions,
            win_frequency_days=venue.win_frequency_days,
            parent_venue_id=venue.parent_venue_id,
            parent_venue_name=venue.parent.name if venue.parent else None,
            children=[
                VenueRef(id=c.id, name=c.name)
                for c in sorted(venue.children, key=lambda c: venue_sort_key(c.name))
            ],
            effective_win_frequency_days=venue.effective_win_frequency_days,
            win_frequency_shared_with=(
                venue.sister_venue_names if venue.effective_win_frequency_days else []
            ),
            venue_type=venue.venue_type,
            default_wheelchair_accessible=venue.default_wheelchair_accessible,
            default_age_restriction=venue.default_age_restriction,
            default_movie_rating=venue.default_movie_rating,
            default_num_pass_pairs=venue.default_num_pass_pairs,
            requires_phone_number=venue.requires_phone_number,
            email_address_requirement=venue.email_address_requirement,
            requires_email_address=venue.requires_email_address,
            staff_guest_requires_name=venue.staff_guest_requires_name,
            hold_close_notifications=venue.hold_close_notifications,
            track_pass_call_in=venue.track_pass_call_in,
            default_lottery_enabled=venue.default_lottery_enabled,
            default_lottery_window_hours=venue.default_lottery_window_hours,
            default_dj_preassign_prohibition_days=venue.default_dj_preassign_prohibition_days,
            default_close_hours_before_show=venue.default_close_hours_before_show,
            default_on_air_description=venue.default_on_air_description,
            default_caller_special_instructions=venue.default_caller_special_instructions,
            default_staff_instructions=venue.default_staff_instructions,
            has_logo=bool(venue.logo_filename),
            show_name_with_logo=venue.show_name_with_logo,
            promoter_id=venue.promoter_id,
            promoter=(
                PromoterResponse.from_orm_promoter(venue.promoter)
                if venue.promoter
                else None
            ),
            shows_have_external_promoter=venue.shows_have_external_promoter,
            owner_emails=[o.promotions_staff_email for o in venue.owners],
            owner_details=[
                VenueOwnerInfo(email=o.staff.email, name=o.staff.name)
                for o in venue.owners
                if o.staff
            ],
            contacts=[VenueContactResponse.model_validate(c) for c in venue.contacts],
        )
