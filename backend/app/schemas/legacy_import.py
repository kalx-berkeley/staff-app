"""Schemas for the legacy paper-form data import feature."""

from datetime import date, time
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class OnAirWinnerImport(BaseModel):
    """On-air winner data from a paper form."""

    recipient_name: str = Field(..., min_length=1, max_length=200)
    recipient_phone: str = Field(..., min_length=1, max_length=20)
    recipient_email: Optional[str] = Field(None, max_length=200)
    given_away_by_dj: Optional[str] = Field(None, max_length=200)


class StaffPassImport(BaseModel):
    """A staff pass claim, optionally with a +1 guest."""

    staff_id: int
    has_guest: bool = False
    guest_name: Optional[str] = Field(None, max_length=200)


class LegacyShowImport(BaseModel):
    """Full historical show import from a paper form."""

    event_name: str = Field(..., min_length=1, max_length=200)
    genre: list[str] = Field(default_factory=list)
    venue_id: int = Field(..., gt=0)
    show_date: date
    show_time: Optional[time] = None
    show_start_date: Optional[date] = None
    on_air_description: Optional[str] = Field(None, max_length=2000)
    caller_special_instructions: Optional[str] = Field(None, max_length=1000)
    age_restriction: Literal["all_ages", "18+", "21+"] = "all_ages"
    wheelchair_accessible: bool = True
    num_pass_pairs: int = Field(..., ge=1, le=5)
    co_announce: bool = False
    on_air_winners: list[OnAirWinnerImport] = Field(default_factory=list)
    staff_passes: list[StaffPassImport] = Field(default_factory=list)

    @field_validator("genre", mode="before")
    @classmethod
    def normalize_genre_case(cls, v: list[str]) -> list[str]:
        return [g.lower() for g in v]


class LegacyImportResult(BaseModel):
    """Result of a legacy show import."""

    show_id: int
    on_air_winners_created: int
    staff_passes_claimed: int
