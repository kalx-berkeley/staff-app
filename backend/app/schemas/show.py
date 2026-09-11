"""Pydantic schemas for Show API."""

from datetime import date, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.types import UtcDatetime
from app.schemas.lottery import LotteryEntryResponse


class ShowBandCreate(BaseModel):
    """Schema for creating or updating a band annotation on a show."""

    musicbrainz_id: str = Field(..., description="MusicBrainz Artist MBID (UUID)")
    band_name: str = Field(
        ..., min_length=1, max_length=300, description="Canonical artist name"
    )
    start_pos: int = Field(..., ge=0, description="Start character position in event_name")
    end_pos: int = Field(..., ge=1, description="End character position in event_name")
    artist_type: str | None = None
    artist_country: str | None = None
    artist_disambiguation: str | None = None
    artist_tags: list[str] | None = None


class ShowBandResponse(BaseModel):
    """Schema for a band annotation on a show."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    show_id: int
    musicbrainz_id: str
    band_name: str
    start_pos: int
    end_pos: int
    artist_type: str | None
    artist_country: str | None
    artist_disambiguation: str | None
    artist_tags: list[str] | None


class ShowCreate(BaseModel):
    """Schema for creating a new show."""

    event_name: str = Field(..., min_length=1, max_length=200, description="Event name")
    genre: list[str] | None = Field(None, description="Music genres")
    venue_id: int = Field(..., gt=0, description="Reference to existing venue")
    promoter_id: int | None = Field(
        None, description="Promoter for this show; overrides the venue's default promoter"
    )
    show_date: date = Field(
        ..., description="Date of the show (or end date for multi-day shows)"
    )
    show_time: time | None = Field(
        None, description="Time of the show (omit for multi-day shows)"
    )
    show_start_date: date | None = Field(None, description="Start date for multi-day shows")
    on_air_description: str | None = Field(
        None, max_length=2000, description="On-air description of the show"
    )
    caller_special_instructions: str | None = Field(
        None, max_length=1000, description="Caller special instructions for the show"
    )
    age_restriction: Literal["all_ages", "18+", "21+"] = Field(
        ..., description="Age restriction"
    )
    wheelchair_accessible: bool = Field(
        ..., description="Whether the venue is wheelchair accessible"
    )
    num_pass_pairs: int = Field(..., ge=1, le=5, description="Number of pass pairs (1-5)")
    planned_close_date: date | None = Field(None, description="Date to close the show")
    planned_close_time: time | None = Field(
        None, description="Time to close the show (Pacific)"
    )
    auto_close: bool = Field(
        False, description="Automatically close show at planned close time"
    )
    co_announce: bool = Field(False, description="Whether this is a Co-Announce show")
    lottery_enabled: bool = Field(
        False, description="Enable lottery for staff claims and DJ pre-assignments"
    )
    lottery_window_hours: int = Field(
        24, ge=1, description="Hours after publication during which the lottery is open"
    )
    dj_preassign_prohibition_days: int | None = Field(
        None,
        description="Days before planned close date during which DJs cannot self-assign",
    )
    bands: list[ShowBandCreate] = Field(
        default_factory=list, description="Band annotations"
    )

    @field_validator("genre", mode="before")
    @classmethod
    def normalize_genre_case(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        return [g.lower() for g in v]

    @model_validator(mode="after")
    def validate_time_required_for_single_day(self) -> "ShowCreate":
        if self.show_start_date is None and self.show_time is None:
            raise ValueError("show_time is required when show_start_date is not provided")
        return self

    @model_validator(mode="after")
    def validate_auto_close_requires_planned_close(self) -> "ShowCreate":
        if self.auto_close and (
            self.planned_close_date is None or self.planned_close_time is None
        ):
            raise ValueError(
                "planned_close_date and planned_close_time are required when auto_close is"
                " True"
            )
        return self

    @model_validator(mode="after")
    def validate_close_before_show(self) -> "ShowCreate":
        if self.planned_close_date is None:
            return self
        effective_show_date = (
            self.show_start_date if self.show_start_date is not None else self.show_date
        )
        effective_show_time = None if self.show_start_date is not None else self.show_time
        if self.planned_close_date > effective_show_date or (
            self.planned_close_date == effective_show_date
            and (
                effective_show_time is None
                or (
                    self.planned_close_time is not None
                    and self.planned_close_time >= effective_show_time
                )
            )
        ):
            raise ValueError("planned close date/time must be before the show date/time")
        return self


class ShowUpdate(BaseModel):
    """Schema for updating an existing show."""

    event_name: str | None = Field(
        None, min_length=1, max_length=200, description="Event name"
    )
    genre: list[str] | None = Field(None, description="Music genres")
    venue_id: int | None = Field(None, gt=0, description="Reference to existing venue")
    promoter_id: int | None = Field(
        None, description="Promoter for this show; overrides the venue's default promoter"
    )
    show_date: date | None = Field(
        None, description="Date of the show (or end date for multi-day shows)"
    )
    show_time: time | None = Field(
        None, description="Time of the show (omit for multi-day shows)"
    )
    show_start_date: date | None = Field(None, description="Start date for multi-day shows")
    on_air_description: str | None = Field(
        None, max_length=2000, description="On-air description of the show"
    )
    caller_special_instructions: str | None = Field(
        None, max_length=1000, description="Caller special instructions for the show"
    )
    age_restriction: Literal["all_ages", "18+", "21+"] | None = Field(
        None, description="Age restriction"
    )
    wheelchair_accessible: bool | None = Field(
        None, description="Whether the venue is wheelchair accessible"
    )
    num_pass_pairs: int | None = Field(
        None, ge=1, le=5, description="Number of pass pairs (1-5)"
    )
    planned_close_date: date | None = Field(None, description="Date to close the show")
    planned_close_time: time | None = Field(
        None, description="Time to close the show (Pacific)"
    )
    auto_close: bool | None = Field(
        None, description="Automatically close show at planned close time"
    )
    co_announce: bool | None = Field(None, description="Whether this is a Co-Announce show")
    lottery_enabled: bool | None = Field(
        None, description="Enable lottery for staff claims and DJ pre-assignments"
    )
    lottery_window_hours: int | None = Field(
        None, ge=1, description="Hours after publication during which the lottery is open"
    )
    dj_preassign_prohibition_days: int | None = Field(
        None,
        description="Days before planned close date during which DJs cannot self-assign",
    )
    bands: list[ShowBandCreate] | None = Field(
        None, description="Replace band list; omit to leave unchanged"
    )

    @field_validator("genre", mode="before")
    @classmethod
    def normalize_genre_case(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        return [g.lower() for g in v]


class AffectedStaffMember(BaseModel):
    """A staff member who lost a claimed pass due to a pass count reduction."""

    name: str
    phone: str | None
    email: str | None


class PassAdjustmentResult(BaseModel):
    """Result of a pass count adjustment, listing affected DJs and staff."""

    affected_djs: list[str]
    affected_staff: list[AffectedStaffMember]


class ShowAttemptResponse(BaseModel):
    """Schema for a failed pass giveaway attempt."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    dj_name: str
    attempted_at: UtcDatetime


class DescriptionAnalysisRequest(BaseModel):
    """Schema for requesting a value-neutrality check of an on-air description."""

    text: str = Field("", max_length=2000, description="On-air description text to analyze")


class DescriptionFinding(BaseModel):
    """A phrase in an on-air description that may not be value neutral."""

    model_config = ConfigDict(from_attributes=True)

    category: Literal[
        "terminology",
        "call_to_action",
        "comparative",
        "endorsement",
        "hype",
        "emphasis",
        "subjective",
    ]
    severity: Literal["high", "medium", "low"]
    phrase: str
    start: int
    end: int
    message: str
    suggestion: str


class DescriptionAnalysisResponse(BaseModel):
    """Schema for the result of analyzing an on-air description."""

    model_config = ConfigDict(from_attributes=True)

    findings: list[DescriptionFinding]
    sentiment_compound: float = Field(
        ..., description="VADER compound sentiment of the evaluative text, -1 to 1"
    )
    sentiment_positive: float = Field(
        ..., description="Share of the evaluative text scored as positive, 0 to 1"
    )
    reads_promotional: bool = Field(
        ..., description="Whether the description reads as enthusiastic overall"
    )
    summary: str


class PromotionsContact(BaseModel):
    """Contact info for a promotions staff owner of the venue."""

    email: str
    name: str
    phone: str


class ShowResponse(BaseModel):
    """Schema for show response with nested venue and promotions contacts."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    event_name: str
    genre: list[str] | None
    venue: "VenueResponse"
    promoter_id: int | None = None
    show_date: date
    show_time: time | None
    show_start_date: date | None
    on_air_description: str | None
    caller_special_instructions: str | None
    age_restriction: str
    wheelchair_accessible: bool
    num_pass_pairs: int
    promotions_contacts: list[PromotionsContact] = Field(
        default_factory=list,
        description="Promotions staff contacts (effective promoter owners)",
    )
    status: str
    available_pair_count: int = Field(
        default=0, description="Number of available pass pairs"
    )
    available_staff_count: int = Field(
        default=0, description="Number of available staff passes"
    )
    passes: list["PassResponse"] = Field(
        default_factory=list, description="All passes for this show"
    )
    attempts: list[ShowAttemptResponse] = Field(
        default_factory=list, description="Failed giveaway attempts for this show"
    )
    planned_close_date: date | None
    planned_close_time: time | None
    auto_close: bool
    co_announce: bool
    lottery_enabled: bool = False
    lottery_window_hours: int = 24
    dj_preassign_prohibition_days: int | None = None
    published_at: UtcDatetime | None = None
    my_lottery_entry: LotteryEntryResponse | None = None
    pass_adjustment: PassAdjustmentResult | None = None
    bands: list[ShowBandResponse] = Field(
        default_factory=list, description="Band annotations"
    )
    is_mine: bool = False


class VenueShowSummary(BaseModel):
    """Minimal venue info for the show list view."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class ShowSummary(BaseModel):
    """Lean show schema for list endpoints — no passes or attempts arrays."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    event_name: str
    genre: list[str] | None
    venue: VenueShowSummary
    show_date: date
    show_time: time | None
    show_start_date: date | None
    caller_special_instructions: str | None
    age_restriction: str
    wheelchair_accessible: bool
    status: str
    num_pass_pairs: int
    available_pair_count: int = 0
    available_staff_count: int = 0
    guest_hold_staff_count: int = 0
    co_announce: bool
    published_at: UtcDatetime | None = None
    bands: list[ShowBandResponse] = Field(default_factory=list)
    is_mine: bool = False


# Import PassResponse and VenueResponse after ShowResponse to avoid circular import
from app.schemas.pass_schema import PassResponse
from app.schemas.venue import VenueResponse

ShowResponse.model_rebuild()
