"""Schemas for KALX Staff Analytics."""

from datetime import date
from typing import Any, Optional

from pydantic import BaseModel, Field


class AnalyticsWindow(BaseModel):
    start: date
    end: date
    preset: Optional[str]
    label: str


class AnalyticsTabResponse(BaseModel):
    """One analytics page: its window, an optional title and its metrics."""

    window: AnalyticsWindow
    title: Optional[str] = None
    # Metric dicts from `analytics_metrics`; their shape depends on their kind
    metrics: list[dict[str, Any]]


class ActiveDayBeacon(BaseModel):
    """Sent by the SPA on the first page load of the day in each sub-site."""

    subsite: str = Field(..., max_length=32)
