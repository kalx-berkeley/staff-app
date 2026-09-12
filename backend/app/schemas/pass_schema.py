"""Pydantic schemas for Pass API."""

from datetime import date
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.types import UtcDatetime


class WinnerReleaseData(BaseModel):
    """Schema for releasing a pass winner back to available."""

    reason: str = Field(
        ..., min_length=1, max_length=2000, description="Reason for releasing the passes"
    )
    releasing_name: str | None = Field(
        None,
        max_length=100,
        description="Name of person releasing (required when not authenticated)",
    )
    releasing_email: str | None = Field(
        None,
        max_length=200,
        description="Email of person releasing (required when not authenticated)",
    )


class GiveawayData(BaseModel):
    """Schema for recording a pass giveaway."""

    recipient_name: str = Field(
        ..., min_length=1, max_length=100, description="Winner's name"
    )
    recipient_phone: str = Field(
        ..., min_length=1, max_length=20, description="Winner's phone number"
    )
    recipient_email: str | None = Field(
        None, max_length=200, description="Winner's email address (required by some venues)"
    )
    given_away_by_dj: str = Field(
        ..., min_length=1, max_length=100, description="DJ who gave away the passes"
    )


class PreassignmentData(BaseModel):
    """Schema for pre-assigning a pass pair to a DJ."""

    dj_name: str = Field(..., min_length=1, max_length=100, description="DJ name to assign")
    assignment_date: date = Field(..., description="Date for the assignment")


class SelfPreassignmentData(BaseModel):
    """Schema for a Sublist DJ pre-assigning a pass pair to themselves or a specialty show."""

    assignment_date: date = Field(..., description="Date for the assignment")
    specialty_show_id: int | None = Field(
        None,
        description=(
            "Optional specialty show ID to reserve for. The DJ must be a member of this"
            " show."
        ),
    )
    dj_name_override: str | None = Field(
        None,
        description=(
            "Optional specific DJ name to use when the staff member has multiple names."
            " Must be one of the names in their dj_name field."
        ),
    )


class DjSuggestion(BaseModel):
    """Schema for a suggested DJ/specialty-show name to pre-assign a pass pair to."""

    name: str
    is_specialty: bool = False
    matched_genres: list[str] = Field(default_factory=list)


class ClaimData(BaseModel):
    """Schema for claiming a staff pass, optionally with a +1 guest."""

    has_guest: bool = Field(False, description="Claim a second pass as a guest hold")
    guest_name: str | None = Field(
        None, max_length=100, description="Guest's name (required by some venues)"
    )
    only_attend_with_guest: bool = Field(
        False,
        description="Release this pass too if the guest cannot attend",
    )


class PassResponse(BaseModel):
    """Schema for pass_item response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    show_id: int
    pass_type: str  # "pair" or "staff"
    status: str  # "available", "given_away", "claimed"

    # For pass pairs given away on-air
    recipient_name: str | None = None
    recipient_phone: str | None = None
    recipient_email: str | None = None
    given_away_by_dj: str | None = None
    given_away_at: UtcDatetime | None = None

    # For staff passes claimed
    staff_id: int | None = None
    staff_name: str | None = None
    staff_phone: str | None = None
    staff_email: str | None = None
    claimed_at: UtcDatetime | None = None

    # Staff +1 guest fields
    has_guest: bool = False
    guest_name: str | None = None
    only_attend_with_guest: bool = False
    guest_of_pass_id: int | None = None

    # For pre-assigned pairs
    preassigned_dj: str | None = None
    preassigned_date: date | None = None
    preassigned_by_staff_id: int | None = None
    preassigned_specialty_show_id: int | None = None
    preassigned_specialty_show_name: str | None = None

    # Show details (populated via relationship)
    show_event_name: str | None = None
    show_date: date | None = None
    show_venue_name: str | None = None
    show_status: str | None = None

    created_at: UtcDatetime
    updated_at: UtcDatetime
