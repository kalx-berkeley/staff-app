"""Tests for KalxLiveService: ICS parsing and matching."""

from datetime import date, datetime, time, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from app.config import settings
from app.models.job_log import JobLog
from app.models.kalx_live_appearance import KalxLiveAppearance
from app.models.show import Show
from app.models.show_band import ShowBand
from app.models.venue import Venue
from app.services.kalx_live_service import KalxLiveIndex, KalxLiveService

_ICS_HEADER = (
    "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//Google Inc//Google Calendar 70.9054//EN\n"
)
_ICS_FOOTER = "END:VCALENDAR\n"


def _vevent(summary: str, dtstart: str = "20250308T190000", uid: str = "evt1") -> str:
    return (
        "BEGIN:VEVENT\n"
        f"DTSTART;TZID=America/Los_Angeles:{dtstart}\n"
        f"DTEND;TZID=America/Los_Angeles:{dtstart}\n"
        f"UID:{uid}@google.com\n"
        "STATUS:CONFIRMED\n"
        f"SUMMARY:{summary}\n"
        "END:VEVENT\n"
    )


class TestParseIcs:
    def test_standard_band_title_is_parsed(self):
        ics = _ICS_HEADER + _vevent("Lady Starbeast on KALX Live!") + _ICS_FOOTER
        rows = KalxLiveService.parse_ics(ics.encode())
        assert rows == [{"band_name": "Lady Starbeast", "event_date": date(2025, 3, 8)}]

    def test_placeholder_band_is_skipped(self):
        ics = _ICS_HEADER + _vevent("[band] on KALX Live!") + _ICS_FOOTER
        assert KalxLiveService.parse_ics(ics.encode()) == []

    def test_cancelled_show_is_skipped(self):
        ics = _ICS_HEADER + _vevent("CANCELLED: Phantom Witch on KALX Live!") + _ICS_FOOTER
        assert KalxLiveService.parse_ics(ics.encode()) == []

    def test_non_matching_title_is_skipped(self):
        ics = _ICS_HEADER + _vevent("Engineering Training") + _ICS_FOOTER
        assert KalxLiveService.parse_ics(ics.encode()) == []

    def test_title_missing_the_word_on_is_skipped(self):
        """A real (but typo'd) calendar title, e.g. "Olivine KALX Live!" missing
        "on" — per product requirement, only the exact format is matched."""
        ics = _ICS_HEADER + _vevent("Olivine KALX Live!") + _ICS_FOOTER
        assert KalxLiveService.parse_ics(ics.encode()) == []

    def test_recurring_master_with_placeholder_title_is_skipped_without_expansion(self):
        """A weekly-recurring master VEVENT (RRULE) with the placeholder title,
        alongside override VEVENTs for individual booked dates — modeled on the
        real calendar's structure. The master must not be expanded/counted."""
        master = (
            "BEGIN:VEVENT\n"
            "DTSTART;TZID=America/Los_Angeles:20230805T190000\n"
            "DTEND;TZID=America/Los_Angeles:20230805T235900\n"
            "RRULE:FREQ=WEEKLY;UNTIL=20240622T065959Z;BYDAY=SA\n"
            "UID:756jt5o5civ3ltm7o1n5kfvktf@google.com\n"
            "STATUS:CONFIRMED\n"
            "SUMMARY:[band] on KALX Live!\n"
            "END:VEVENT\n"
        )
        override1 = (
            "BEGIN:VEVENT\n"
            "DTSTART;TZID=America/Los_Angeles:20240217T190000\n"
            "DTEND;TZID=America/Los_Angeles:20240217T235900\n"
            "UID:756jt5o5civ3ltm7o1n5kfvktf@google.com\n"
            "RECURRENCE-ID;TZID=America/Los_Angeles:20240217T190000\n"
            "STATUS:CONFIRMED\n"
            "SUMMARY:Country Risqu\xe9 on KALX Live!\n"
            "END:VEVENT\n"
        )
        override2 = (
            "BEGIN:VEVENT\n"
            "DTSTART;TZID=America/Los_Angeles:20240406T190000\n"
            "DTEND;TZID=America/Los_Angeles:20240406T235900\n"
            "UID:756jt5o5civ3ltm7o1n5kfvktf@google.com\n"
            "RECURRENCE-ID;TZID=America/Los_Angeles:20240406T190000\n"
            "STATUS:CONFIRMED\n"
            "SUMMARY:Meat Cube on KALX Live!\n"
            "END:VEVENT\n"
        )
        ics = _ICS_HEADER + master + override1 + override2 + _ICS_FOOTER
        rows = KalxLiveService.parse_ics(ics.encode())
        assert rows == [
            {"band_name": "Country Risqu\xe9", "event_date": date(2024, 2, 17)},
            {"band_name": "Meat Cube", "event_date": date(2024, 4, 6)},
        ]

    def test_multiple_appearances_for_same_band_are_both_kept(self):
        ics = (
            _ICS_HEADER
            + _vevent(
                "RETROSPECTACULAR on KALX Live!", dtstart="20241228T190000", uid="evtA"
            )
            + _vevent(
                "RETROSPECTACULAR on KALX Live!", dtstart="20251227T190000", uid="evtB"
            )
            + _ICS_FOOTER
        )
        rows = KalxLiveService.parse_ics(ics.encode())
        assert rows == [
            {"band_name": "RETROSPECTACULAR", "event_date": date(2024, 12, 28)},
            {"band_name": "RETROSPECTACULAR", "event_date": date(2025, 12, 27)},
        ]


@pytest.fixture
def test_venue(db: Session):
    venue = Venue(name="Test Venue", address="123 Test St")
    db.add(venue)
    db.commit()
    db.refresh(venue)
    return venue


class TestFindMatches:
    def _appearance(
        self, db: Session, band_name: str, event_date: date
    ) -> KalxLiveAppearance:
        appearance = KalxLiveAppearance(band_name=band_name, event_date=event_date)
        db.add(appearance)
        db.commit()
        db.refresh(appearance)
        return appearance

    def _show(self, db: Session, test_venue, event_name: str, band_name: str | None):
        show = Show(
            event_name=event_name,
            venue_id=test_venue.id,
            show_date=date(2026, 12, 31),
            show_time=time(20, 0),
            age_restriction="all_ages",
            wheelchair_accessible=True,
            num_pass_pairs=2,
        )
        db.add(show)
        db.flush()
        if band_name:
            db.add(
                ShowBand(
                    show_id=show.id,
                    musicbrainz_id="fake-mbid",
                    band_name=band_name,
                    start_pos=0,
                    end_pos=10,
                )
            )
        db.commit()
        db.refresh(show)
        return show

    def test_recent_past_appearance_matches(self, db: Session, test_venue):
        appearance = self._appearance(db, "Warm Spell", date.today() - timedelta(days=30))
        show = self._show(db, test_venue, "Warm Spell show", "Warm Spell")

        index = KalxLiveService.build_index(db)
        matches = KalxLiveService.find_matches(index, show)
        assert [a.id for a in matches] == [appearance.id]

    def test_future_appearance_matches_with_no_upper_bound(self, db: Session, test_venue):
        appearance = self._appearance(db, "Warm Spell", date.today() + timedelta(days=400))
        show = self._show(db, test_venue, "Warm Spell show", "Warm Spell")

        index = KalxLiveService.build_index(db)
        matches = KalxLiveService.find_matches(index, show)
        assert [a.id for a in matches] == [appearance.id]

    def test_appearance_older_than_60_days_is_excluded(self, db: Session, test_venue):
        self._appearance(db, "Warm Spell", date.today() - timedelta(days=90))
        show = self._show(db, test_venue, "Warm Spell show", "Warm Spell")

        index = KalxLiveService.build_index(db)
        assert KalxLiveService.find_matches(index, show) == []

    def test_appearance_just_under_60_days_old_matches(self, db: Session, test_venue):
        appearance = self._appearance(db, "Warm Spell", date.today() - timedelta(days=59))
        show = self._show(db, test_venue, "Warm Spell show", "Warm Spell")

        index = KalxLiveService.build_index(db)
        matches = KalxLiveService.find_matches(index, show)
        assert [a.id for a in matches] == [appearance.id]

    def test_fuzzy_tagged_band_matches_case_and_typo(self, db: Session, test_venue):
        appearance = self._appearance(db, "Warm Spell", date.today())
        show = self._show(db, test_venue, "show", "warm spel")

        index = KalxLiveService.build_index(db)
        matches = KalxLiveService.find_matches(index, show)
        assert [a.id for a in matches] == [appearance.id]

    def test_event_name_fuzzy_fallback_when_no_bands(self, db: Session, test_venue):
        appearance = self._appearance(db, "Warm Spell", date.today())
        show = self._show(db, test_venue, "Warm Spell w/ Special Guests", None)

        index = KalxLiveService.build_index(db)
        matches = KalxLiveService.find_matches(index, show)
        assert [a.id for a in matches] == [appearance.id]

    def test_single_word_band_does_not_match_via_event_name_fallback(
        self, db: Session, test_venue
    ):
        self._appearance(db, "Nothing", date.today())
        show = self._show(db, test_venue, "Wild Nothing", None)

        index = KalxLiveService.build_index(db)
        assert KalxLiveService.find_matches(index, show) == []

    def test_no_match_returns_empty(self, db: Session, test_venue):
        self._appearance(db, "Completely Unrelated Band", date.today())
        show = self._show(db, test_venue, "A Totally Different Show", None)

        index = KalxLiveService.build_index(db)
        assert KalxLiveService.find_matches(index, show) == []

    def test_empty_index_returns_empty(self, db: Session, test_venue):
        show = self._show(db, test_venue, "Some Show", None)
        assert KalxLiveService.find_matches(KalxLiveIndex(), show) == []


class TestIsConfiguredAndSync:
    def test_is_configured_requires_calendar_id(self, monkeypatch):
        monkeypatch.setattr(settings, "kalx_live_calendar_id", None)
        assert KalxLiveService.is_configured() is False

        monkeypatch.setattr(settings, "kalx_live_calendar_id", "some-calendar-id")
        assert KalxLiveService.is_configured() is True

    def test_sync_no_ops_when_not_configured(self, db: Session, monkeypatch):
        monkeypatch.setattr(settings, "kalx_live_calendar_id", None)

        count = KalxLiveService.sync_kalx_live(db, trigger="scheduled")

        assert count == 0
        assert db.query(KalxLiveAppearance).count() == 0
        assert db.query(JobLog).filter(JobLog.job_id == "kalx_live_sync").count() == 0


class TestNeedsSync:
    def test_no_data_needs_sync(self, db: Session):
        assert KalxLiveService.needs_sync(db) is True

    def test_fresh_data_does_not_need_sync(self, db: Session):
        appearance = KalxLiveAppearance(band_name="Some Band", event_date=date.today())
        db.add(appearance)
        db.commit()
        db.refresh(appearance)
        appearance.fetched_at = datetime.now(timezone.utc) - timedelta(hours=1)
        db.commit()

        assert KalxLiveService.needs_sync(db) is False

    def test_stale_data_needs_sync(self, db: Session):
        appearance = KalxLiveAppearance(band_name="Some Band", event_date=date.today())
        db.add(appearance)
        db.commit()
        db.refresh(appearance)
        appearance.fetched_at = datetime.now(timezone.utc) - timedelta(days=1, minutes=1)
        db.commit()

        assert KalxLiveService.needs_sync(db) is True

    def test_data_just_under_a_day_old_does_not_need_sync(self, db: Session):
        appearance = KalxLiveAppearance(band_name="Some Band", event_date=date.today())
        db.add(appearance)
        db.commit()
        db.refresh(appearance)
        appearance.fetched_at = datetime.now(timezone.utc) - timedelta(hours=23, minutes=59)
        db.commit()

        assert KalxLiveService.needs_sync(db) is False
