"""Pydantic schemas for Lottery API."""

from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.types import UtcDatetime


class StaffLotteryEntryCreate(BaseModel):
    """Body for entering the staff pass lottery."""

    has_guest: bool = False
    guest_name: str | None = None
    only_attend_with_guest: bool = False


class DJLotteryEntryCreate(BaseModel):
    """Body for entering the DJ pass-pair lottery."""

    assignment_date: date = Field(
        ..., description="Air date the DJ wants the pass pair for"
    )
    specialty_show_id: int | None = Field(
        None, description="Optional specialty show ID to reserve under instead of DJ name"
    )
    dj_name_override: str | None = Field(
        None,
        description=(
            "Optional specific DJ name to use when the staff member has multiple names."
            " Must be one of the names in their dj_name field."
        ),
    )


class LotteryEntryResponse(BaseModel):
    """Response schema for a single lottery entry."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    show_id: int
    entry_type: str
    staff_id: int | None
    staff_name: str | None = None
    dj_name: str | None
    specialty_show_id: int | None = None
    assignment_date: date | None
    has_guest: bool
    guest_name: str | None
    only_attend_with_guest: bool
    status: str
    entered_at: UtcDatetime


class LotteryStatusResponse(BaseModel):
    """Response schema for the lottery status of a show."""

    is_active: bool
    deadline: datetime | None
    staff_entry_count: int
    dj_entry_count: int
    my_staff_entry: LotteryEntryResponse | None = None
    my_dj_entry: LotteryEntryResponse | None = None
    # Populated for promotions staff only
    all_staff_entries: list[LotteryEntryResponse] | None = None
    all_dj_entries: list[LotteryEntryResponse] | None = None
