"""Tests for showing datetimes in Pacific time."""

from datetime import datetime, timezone

from app.common.pacific_time import format_pacific_datetime, to_pacific


def test_a_naive_datetime_is_read_as_utc():
    # 03:05 UTC on Nov 13 is 7:05pm Pacific (PST) on Nov 12
    assert (
        format_pacific_datetime(datetime(2026, 11, 13, 3, 5, 59, 123456))
        == "Thu, Nov 12, 2026 at 7:05pm"
    )


def test_an_aware_datetime_is_converted():
    # Daylight saving time: UTC-7
    dt = datetime(2026, 7, 4, 19, 0, tzinfo=timezone.utc)
    assert format_pacific_datetime(dt) == "Sat, Jul 4, 2026 at 12:00pm"


def test_midnight_and_morning():
    assert (
        format_pacific_datetime(datetime(2026, 1, 1, 8, 0)) == "Thu, Jan 1, 2026 at 12:00am"
    )
    assert (
        format_pacific_datetime(datetime(2026, 1, 1, 17, 30))
        == "Thu, Jan 1, 2026 at 9:30am"
    )


def test_to_pacific():
    assert to_pacific(datetime(2026, 1, 1, 8, 0)).hour == 0
