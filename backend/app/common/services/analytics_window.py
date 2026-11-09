"""The time window a KALX Staff Analytics page is showing."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from app.common.services.tracking_service import PACIFIC, pacific_day_start_utc

PRESETS = {
    "last_30_days": "Last 30 days",
    "last_month": "Last month",
    "this_quarter": "This quarter",
    "last_quarter": "Last quarter",
    "this_year": "This year",
    "last_year": "Last year",
    "all_time": "All time",
}
DEFAULT_PRESET = "last_30_days"

# "All time" starts here, well before the app's first show
ALL_TIME_START = date(2000, 1, 1)


@dataclass(frozen=True)
class Window:
    """Pacific dates from *start* to *end*, inclusive."""

    start: date
    end: date
    preset: Optional[str]

    @property
    def label(self) -> str:
        if self.preset:
            return PRESETS[self.preset]
        return f"{self.start.isoformat()} to {self.end.isoformat()}"

    @property
    def start_utc(self) -> datetime:
        """The window's first instant, as a naive UTC datetime."""
        return pacific_day_start_utc(self.start)

    @property
    def end_utc(self) -> datetime:
        """The instant after the window ends, as a naive UTC datetime."""
        return pacific_day_start_utc(self.end + timedelta(days=1))

    def contains(self, dt: datetime) -> bool:
        """Whether UTC datetime *dt* (naive or aware) falls in the window."""
        naive = dt.astimezone(timezone.utc).replace(tzinfo=None) if dt.tzinfo else dt
        return self.start_utc <= naive < self.end_utc

    def contains_date(self, d: date) -> bool:
        return self.start <= d <= self.end


def today_pacific() -> date:
    return datetime.now(PACIFIC).date()


def _quarter_start(d: date) -> date:
    return date(d.year, 3 * ((d.month - 1) // 3) + 1, 1)


def preset_window(preset: str, today: date) -> Window:
    """The dates *preset* covers on *today*."""
    if preset == "last_30_days":
        return Window(today - timedelta(days=29), today, preset)
    if preset == "last_month":
        end = today.replace(day=1) - timedelta(days=1)
        return Window(end.replace(day=1), end, preset)
    if preset == "this_quarter":
        return Window(_quarter_start(today), today, preset)
    if preset == "last_quarter":
        end = _quarter_start(today) - timedelta(days=1)
        return Window(_quarter_start(end), end, preset)
    if preset == "this_year":
        return Window(date(today.year, 1, 1), today, preset)
    if preset == "last_year":
        return Window(date(today.year - 1, 1, 1), date(today.year - 1, 12, 31), preset)
    if preset == "all_time":
        return Window(ALL_TIME_START, today, preset)
    raise ValueError(f"Unknown time window {preset!r}")


def parse_window(
    preset: Optional[str],
    start: Optional[date],
    end: Optional[date],
    today: Optional[date] = None,
) -> Window:
    """
    The window a request asks for: a custom *start*–*end* range when both are
    given, otherwise *preset* (default: the last 30 days).

    :raises ValueError: For an unknown preset or a range that ends before it starts.
    """
    today = today or today_pacific()
    if start is not None and end is not None:
        if end < start:
            raise ValueError("The time window ends before it starts")
        return Window(start, end, None)
    return preset_window(preset or DEFAULT_PRESET, today)
