"""Tests for FeatureBinService: CSV parsing, artist transform, and matching."""

from datetime import date, time

import pytest
from sqlalchemy.orm import Session

from app.config import settings
from app.models.feature_bin_release import FeatureBinRelease
from app.models.job_log import JobLog
from app.models.show import Show
from app.models.show_band import ShowBand
from app.models.venue import Venue
from app.services.feature_bin_service import (
    FeatureBinIndex,
    FeatureBinService,
    transform_artist,
)


class TestTransformArtist:
    def test_last_comma_first_is_swapped(self):
        assert transform_artist("Doe, John") == "John Doe"

    def test_extra_whitespace_is_trimmed(self):
        assert transform_artist("  Doe ,  John  ") == "John Doe"

    def test_no_comma_passes_through_unchanged(self):
        assert transform_artist("Mighty Mighty Bosstones") == "Mighty Mighty Bosstones"

    def test_trailing_comma_with_no_first_name_passes_through(self):
        assert transform_artist("Cher,") == "Cher,"

    def test_ampersand_collaborators_keep_leader_name_inverted_only(self):
        assert (
            transform_artist("Ambarchi, Oren & Will Guthrie")
            == "Oren Ambarchi & Will Guthrie"
        )

    def test_and_collaborators_keep_leader_name_inverted_only(self):
        assert (
            transform_artist("Akinmusire, Ambrose and Mary Halvorson")
            == "Ambrose Akinmusire and Mary Halvorson"
        )

    def test_leader_and_band_name_convention(self):
        assert (
            transform_artist("Burnham, Aaron & The Brushfires")
            == "Aaron Burnham & The Brushfires"
        )


class TestParseRows:
    def test_skips_header_rows_and_trims_whitespace(self):
        csv_text = (
            "Group1,,,,,,,,,\n"
            "Added,Artist,Album,Label,Rel'd,Dot,Media,Rev'r,Status,Bandcamp/You Tube Link\n"
            " 3/14 , Some Artist ,  Some Album ,Some Label,2024,RED,CD,ab,Active,"
            "https://example.com \n"
        )
        rows = FeatureBinService.parse_rows(csv_text)
        assert len(rows) == 1
        row = rows[0]
        assert row["added_date"] == "3/14"
        assert row["artist"] == "Some Artist"
        assert row["album"] == "Some Album"
        assert row["media_url"] == "https://example.com"

    def test_quoted_artist_field_with_comma(self):
        csv_text = (
            "Group1,,,,,,,,,\n"
            "Added,Artist,Album,Label,Rel'd,Dot,Media,Rev'r,Status,Bandcamp/You Tube Link\n"
            '3/14,"Doe, John",Some Album,Some Label,2024,RED,CD,ab,Active,\n'
        )
        rows = FeatureBinService.parse_rows(csv_text)
        assert len(rows) == 1
        assert rows[0]["artist"] == "John Doe"
        assert rows[0]["album"] == "Some Album"
        assert rows[0]["dot"] == "RED"

    def test_blank_rows_are_dropped(self):
        csv_text = "Group1,,\nAdded,Artist,Album\n,,\n3/14,Some Artist,Some Album\n"
        rows = FeatureBinService.parse_rows(csv_text)
        assert len(rows) == 1
        assert rows[0]["artist"] == "Some Artist"

    def test_too_few_rows_returns_empty(self):
        assert FeatureBinService.parse_rows("Added,Artist\n") == []


@pytest.fixture
def test_venue(db: Session):
    venue = Venue(name="Test Venue", address="123 Test St")
    db.add(venue)
    db.commit()
    db.refresh(venue)
    return venue


class TestFindMatches:
    def _release(
        self, db: Session, artist: str, album: str = "Some Album"
    ) -> FeatureBinRelease:
        release = FeatureBinRelease(artist=artist, album=album)
        db.add(release)
        db.commit()
        db.refresh(release)
        return release

    def test_exact_tagged_band_matches(self, db: Session, test_venue):
        release = self._release(db, "The Mighty Mighty Bosstones")
        show = Show(
            event_name="Bosstones show",
            venue_id=test_venue.id,
            show_date=date(2024, 12, 31),
            show_time=time(20, 0),
            age_restriction="all_ages",
            wheelchair_accessible=True,
            num_pass_pairs=2,
        )
        db.add(show)
        db.flush()
        db.add(
            ShowBand(
                show_id=show.id,
                musicbrainz_id="fake-mbid",
                band_name="The Mighty Mighty Bosstones",
                start_pos=0,
                end_pos=10,
            )
        )
        db.commit()
        db.refresh(show)

        index = FeatureBinService.build_index(db)
        matches = FeatureBinService.find_matches(index, show)
        assert [r.id for r in matches] == [release.id]

    def test_fuzzy_tagged_band_matches_case_and_typo(self, db: Session, test_venue):
        release = self._release(db, "Mighty Mighty Bosstones")
        show = Show(
            event_name="show",
            venue_id=test_venue.id,
            show_date=date(2024, 12, 31),
            show_time=time(20, 0),
            age_restriction="all_ages",
            wheelchair_accessible=True,
            num_pass_pairs=2,
        )
        db.add(show)
        db.flush()
        db.add(
            ShowBand(
                show_id=show.id,
                musicbrainz_id="fake-mbid",
                band_name="might might bosstones",
                start_pos=0,
                end_pos=10,
            )
        )
        db.commit()
        db.refresh(show)

        index = FeatureBinService.build_index(db)
        matches = FeatureBinService.find_matches(index, show)
        assert [r.id for r in matches] == [release.id]

    def test_event_name_fuzzy_fallback_when_no_bands(self, db: Session, test_venue):
        release = self._release(db, "Mighty Mighty Bosstones")
        show = Show(
            event_name="Mighty Mighty Bosstones w/ Special Guests",
            venue_id=test_venue.id,
            show_date=date(2024, 12, 31),
            show_time=time(20, 0),
            age_restriction="all_ages",
            wheelchair_accessible=True,
            num_pass_pairs=2,
        )
        db.add(show)
        db.commit()
        db.refresh(show)

        index = FeatureBinService.build_index(db)
        matches = FeatureBinService.find_matches(index, show)
        assert [r.id for r in matches] == [release.id]

    def test_no_match_returns_empty(self, db: Session, test_venue):
        self._release(db, "Completely Unrelated Artist")
        show = Show(
            event_name="A Totally Different Show",
            venue_id=test_venue.id,
            show_date=date(2024, 12, 31),
            show_time=time(20, 0),
            age_restriction="all_ages",
            wheelchair_accessible=True,
            num_pass_pairs=2,
        )
        db.add(show)
        db.commit()
        db.refresh(show)

        index = FeatureBinService.build_index(db)
        assert FeatureBinService.find_matches(index, show) == []

    def test_empty_index_returns_empty(self, db: Session, test_venue):
        show = Show(
            event_name="Some Show",
            venue_id=test_venue.id,
            show_date=date(2024, 12, 31),
            show_time=time(20, 0),
            age_restriction="all_ages",
            wheelchair_accessible=True,
            num_pass_pairs=2,
        )
        db.add(show)
        db.commit()
        db.refresh(show)

        assert FeatureBinService.find_matches(FeatureBinIndex(), show) == []


class TestIsConfiguredAndSync:
    def test_is_configured_requires_both_id_and_gid(self, monkeypatch):
        monkeypatch.setattr(settings, "feature_bin_sheet_id", None)
        monkeypatch.setattr(settings, "feature_bin_sheet_gid", None)
        assert FeatureBinService.is_configured() is False

        monkeypatch.setattr(settings, "feature_bin_sheet_id", "some-id")
        monkeypatch.setattr(settings, "feature_bin_sheet_gid", None)
        assert FeatureBinService.is_configured() is False

        monkeypatch.setattr(settings, "feature_bin_sheet_id", "some-id")
        monkeypatch.setattr(settings, "feature_bin_sheet_gid", "some-gid")
        assert FeatureBinService.is_configured() is True

    def test_sync_no_ops_when_not_configured(self, db: Session, monkeypatch):
        monkeypatch.setattr(settings, "feature_bin_sheet_id", None)
        monkeypatch.setattr(settings, "feature_bin_sheet_gid", None)

        count = FeatureBinService.sync_feature_bin(db, trigger="scheduled")

        assert count == 0
        assert db.query(FeatureBinRelease).count() == 0
        assert db.query(JobLog).filter(JobLog.job_id == "feature_bin_sync").count() == 0
