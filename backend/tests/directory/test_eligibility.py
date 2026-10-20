"""Tests for the Sublist DJ requirements' rules (pure functions)."""

from datetime import date, datetime, timedelta

import pytest

from app.common.services.profile_providers import DepartmentHours, MonthHours
from app.directory.services import eligibility as rules
from app.directory.services.eligibility import PACIFIC, Playlist


def _at(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=PACIFIC)


def _playlist(
    pid: int,
    start: datetime,
    minutes: int,
    persona_id: int = 1,
    show_id: int | None = 100,
    automation: bool = False,
    title: str | None = "FREEFORM",
) -> Playlist:
    return Playlist(
        id=pid,
        persona_id=persona_id,
        show_id=show_id,
        start=start,
        end=start + timedelta(minutes=minutes),
        title=title,
        automation=automation,
    )


# --- Quarters ---


@pytest.mark.parametrize(
    "day,start",
    [
        (date(2026, 2, 1), date(2026, 2, 1)),
        (date(2026, 4, 30), date(2026, 2, 1)),
        (date(2026, 5, 1), date(2026, 5, 1)),
        (date(2026, 10, 20), date(2026, 8, 1)),
        (date(2026, 11, 1), date(2026, 11, 1)),
        (date(2026, 12, 31), date(2026, 11, 1)),
        (date(2027, 1, 31), date(2026, 11, 1)),
    ],
)
def test_quarter_start(day, start):
    assert rules.quarter_start(day) == start


def test_quarter_end_and_label_across_the_new_year():
    start = date(2026, 11, 1)
    assert rules.quarter_end(start) == date(2027, 1, 31)
    assert rules.quarter_label(start) == "Nov 2026–Jan 2027"
    assert rules.quarter_label(date(2026, 5, 1)) == "May–Jul 2026"


# --- Shifts ---


def test_a_shift_qualifies_at_90_minutes():
    day = date(2026, 6, 1)
    shifts, checks = rules.find_shifts(
        [_playlist(1, _at(day, 10), 89), _playlist(2, _at(day, 14), 90)], set()
    )
    assert [s.qualifies for s in shifts] == [False, True]
    assert [(c.counted, c.reason) for c in checks] == [
        (False, "too_short"),
        (True, None),
    ]


def test_back_to_back_playlists_make_one_shift():
    day = date(2026, 6, 1)
    shifts, checks = rules.find_shifts(
        [
            _playlist(1, _at(day, 10), 60, title="First hour"),
            _playlist(2, _at(day, 11), 60, title="Second hour"),
        ],
        set(),
    )
    assert len(shifts) == 1
    assert shifts[0].minutes == 120
    assert shifts[0].title == "First hour / Second hour"
    assert all(c.counted and c.shift_minutes == 120 for c in checks)


def test_a_gap_between_playlists_splits_the_shift():
    day = date(2026, 6, 1)
    shifts, _ = rules.find_shifts(
        [_playlist(1, _at(day, 10), 60), _playlist(2, _at(day, 11, 5), 60)], set()
    )
    assert [s.minutes for s in shifts] == [60, 60]
    assert not any(s.qualifies for s in shifts)


def test_specialty_shows_and_automated_playlists_dont_count_or_merge():
    day = date(2026, 6, 1)
    shifts, checks = rules.find_shifts(
        [
            _playlist(1, _at(day, 10), 60),
            _playlist(2, _at(day, 11), 60, show_id=900),
            _playlist(3, _at(day, 12), 60),
            _playlist(4, _at(day, 13), 120, automation=True),
        ],
        {900},
    )
    assert [s.minutes for s in shifts] == [60, 60]
    assert [(c.counted, c.reason) for c in checks] == [
        (False, "too_short"),
        (False, "specialty"),
        (False, "too_short"),
        (False, "automated"),
    ]


def test_a_title_other_than_freeform_is_not_a_specialty_show():
    day = date(2026, 6, 1)
    shifts, _ = rules.find_shifts(
        [_playlist(1, _at(day, 10), 120, title="Night Moves")], {900}
    )
    assert shifts[0].qualifies


def test_own_playlists_leave_out_placeholders_and_other_people():
    day = date(2026, 6, 1)
    playlists = [
        _playlist(1, _at(day, 12), 120, persona_id=1),
        _playlist(2, _at(day, 10), 120, persona_id=176287),
        _playlist(3, _at(day, 8), 120, persona_id=2),
        _playlist(4, _at(day, 6), 120, persona_id=5),
    ]
    own = rules.own_playlists(playlists, [1, 176287, 5], {176287})
    assert [p.id for p in own] == [4, 1]


def test_a_shifts_quarter_is_by_its_pacific_start():
    # 11:30 pm Pacific on Apr 30 is May 1 in UTC, but still Feb–Apr
    shifts, _ = rules.find_shifts(
        [_playlist(1, _at(date(2026, 4, 30), 23, 30), 120)], set()
    )
    assert shifts[0].quarter == date(2026, 2, 1)


# --- Workforms ---


def _month(month, status="locked", departments=(), loa=False) -> MonthHours:
    return MonthHours(
        month=month,
        status=status,
        reported_hours=sum(d.hours for d in departments),
        departments=list(departments),
        loa_overlaps_month=loa,
    )


def test_workform_months_are_the_last_three_complete_months():
    assert rules.workform_months(date(2026, 10, 20)) == [
        date(2026, 9, 1),
        date(2026, 8, 1),
        date(2026, 7, 1),
    ]
    assert rules.workform_months(date(2027, 1, 5))[0] == date(2026, 12, 1)


def test_older_months_count_only_approved_hours():
    check = rules.check_month(
        _month(
            date(2026, 7, 1),
            departments=[
                DepartmentHours("Music", 4, "Approved"),
                DepartmentHours("News", 3, None),
                DepartmentHours("Promotions", 5, "Denied"),
            ],
        ),
        most_recent=False,
    )
    assert check.counted_hours == 4
    assert check.met is False
    assert check.pending_departments == ["News"]


def test_the_most_recent_month_counts_submitted_hours_unless_denied():
    check = rules.check_month(
        _month(
            date(2026, 9, 1),
            status="locked",
            departments=[
                DepartmentHours("Music", 4, "Approved"),
                DepartmentHours("News", 3, None),
                DepartmentHours("Promotions", 5, "Denied"),
            ],
        ),
        most_recent=True,
    )
    assert check.counted_hours == 7
    assert check.met is True
    assert check.pending_departments == []


def test_a_draft_counts_nothing():
    check = rules.check_month(_month(date(2026, 9, 1), status="draft"), most_recent=True)
    assert check.counted_hours == 0
    assert check.met is False


def test_a_leave_month_counts_as_met():
    check = rules.check_month(
        _month(date(2026, 8, 1), status="not_started", loa=True), False
    )
    assert check.met is True
    assert rules.month_summary(check) == "Aug LOA ✓"


# --- DJ Quiz ---

DEADLINES = {2025: date(2025, 7, 31), 2026: date(2026, 9, 30)}


def test_last_years_quiz_counts_until_this_years_deadline():
    quiz = rules.check_quiz([2025], DEADLINES, date(2026, 9, 30))
    assert quiz.met is True
    assert quiz.current_year == 2025
    assert quiz.due == date(2026, 9, 30)


def test_after_the_deadline_only_this_years_quiz_counts():
    assert rules.check_quiz([2025], DEADLINES, date(2026, 10, 1)).met is False
    quiz = rules.check_quiz([2025, 2026], DEADLINES, date(2026, 10, 1))
    assert quiz.met is True
    assert quiz.due is None


def test_this_years_quiz_done_early_counts():
    quiz = rules.check_quiz([2026], DEADLINES, date(2026, 3, 1))
    assert quiz.met is True
    assert quiz.due is None


def test_without_a_deadline_last_years_quiz_keeps_counting():
    quiz = rules.check_quiz([2026], DEADLINES, date(2027, 11, 1))
    assert quiz.met is True
    assert quiz.current_year == 2026
    assert quiz.deadline_announced is False


# --- Eligible until ---


def test_eligible_until_the_end_of_the_quarter_a_shift_covers():
    today = date(2026, 10, 20)
    last_quarter = [_playlist(1, _at(date(2026, 6, 1), 10), 120)]
    shifts, _ = rules.find_shifts(last_quarter, set())
    quiz = rules.check_quiz([2026], DEADLINES, today)
    assert rules.eligible_until(today, shifts, quiz, None) == date(2026, 10, 31)

    this_quarter = last_quarter + [_playlist(2, _at(date(2026, 9, 1), 10), 120)]
    shifts, _ = rules.find_shifts(this_quarter, set())
    assert rules.eligible_until(today, shifts, quiz, None) == date(2027, 1, 31)


def test_eligible_until_the_quiz_deadline_or_a_coming_leave():
    today = date(2026, 9, 1)
    shifts, _ = rules.find_shifts(
        [
            _playlist(1, _at(date(2026, 6, 1), 10), 120),
            _playlist(2, _at(date(2026, 8, 20), 10), 120),
        ],
        set(),
    )
    quiz = rules.check_quiz([2025], DEADLINES, today)
    assert rules.eligible_until(today, shifts, quiz, None) == date(2026, 9, 30)
    assert rules.eligible_until(today, shifts, quiz, date(2026, 9, 15)) == date(2026, 9, 14)
    # A leave that has already started isn't "coming"
    assert rules.eligible_until(today, shifts, quiz, date(2026, 8, 1)) == date(2026, 9, 30)


def test_next_workform_note():
    assert (
        rules.next_workform_note(date(2026, 12, 3))
        == "Keep reporting 6 h a month: December's workform counts from January 1."
    )
