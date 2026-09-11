"""Feature bin sync and matching service.

The KALX music library "feature bin" (recently added releases) is tracked in a
public Google Sheet. This service fetches the "Current Active A-Z" worksheet
nightly, replaces the FeatureBinRelease table with the sheet's current
snapshot, and matches feature-bin artists against shows so the promotions
website can flag shows with a performer who has a release in the bin.
"""

import csv
import io
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import httpx
from rapidfuzz import fuzz, process
from rapidfuzz.utils import default_process
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.models.feature_bin_release import FeatureBinRelease
from app.models.job_log import JobLog

logger = logging.getLogger(__name__)

_SHEET_EXPORT_URL = (
    "https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
)

# How old feature-bin data can get before a fresh sync is considered overdue
# (used by the startup bootstrap check, not the nightly schedule itself).
_STALE_AFTER = timedelta(days=1)

# A tagged artist (from ShowBand) is already an isolated, normalized name, so
# the only slop expected is casing/punctuation — a high threshold avoids false
# positives. An event_name fuzzy fallback needs more slack since it often has
# supporting-act text or venue framing around the headliner.
_BAND_MATCH_THRESHOLD = 90
_EVENT_NAME_MATCH_THRESHOLD = 85

# Maps the sheet's column names (second header row) to FeatureBinRelease fields.
_COLUMN_MAP = {
    "Added": "added_date",
    "Artist": "artist",
    "Album": "album",
    "Label": "label",
    "Rel'd": "released_year",
    "Dot": "dot",
    "Media": "media",
    "Rev'r": "reviewer",
    "Status": "sheet_status",
    "Bandcamp/You Tube Link": "media_url",
}


# Splits "Erskine, Peter & Scott Colley" into a first-name part ("Peter") and a
# trailing collaborator part ("& Scott Colley"), so only the leader's name gets
# inverted and credited collaborators are left as written.
_COLLAB_BOUNDARY_RE = re.compile(r"\s+(&|and)\s+", re.IGNORECASE)


def transform_artist(name: str) -> str:
    """Transform "Last, First" artist names to "First Last".

    Also handles the sheet's "Leader, First & Collaborator(s)" convention
    (e.g. "Burnham, Aaron & The Brushfires" -> "Aaron Burnham & The
    Brushfires") by inverting only the leader's name and leaving credited
    collaborators after an "&"/"and" untouched. Returns the (trimmed) input
    unchanged if it doesn't look like a "Last, First" name. Kept standalone
    so additional transforms can be composed in here later.
    """
    name = name.strip()
    if "," not in name:
        return name
    last, _, rest = name.partition(",")
    last = last.strip()
    rest = rest.strip()
    if not last or not rest:
        return name

    match = _COLLAB_BOUNDARY_RE.search(rest)
    if match:
        first = rest[: match.start()].strip()
        collaborators = rest[match.start() :].strip()
        if first and collaborators:
            return f"{first} {last} {collaborators}"

    return f"{rest} {last}"


@dataclass
class FeatureBinIndex:
    """A snapshot of feature-bin releases used to match against shows."""

    releases: list[FeatureBinRelease] = field(default_factory=list)


class FeatureBinService:
    """Fetches, stores, and matches the KALX feature bin against shows."""

    @staticmethod
    def is_configured() -> bool:
        """Whether FEATURE_BIN_SHEET_ID/FEATURE_BIN_SHEET_GID are set.

        The sheet ID isn't public data, so it has no default in this public
        repo — the feature is simply disabled until both are configured.
        """
        return bool(settings.feature_bin_sheet_id and settings.feature_bin_sheet_gid)

    @staticmethod
    def needs_sync(db: Session) -> bool:
        """Whether the feature bin has no data yet, or its data is more than a day old.

        Used by the startup bootstrap check to catch a freshly deployed
        instance or a long period of scheduler downtime.
        """
        count, latest_fetched_at = db.query(
            func.count(FeatureBinRelease.id), func.max(FeatureBinRelease.fetched_at)
        ).one()
        if count == 0 or latest_fetched_at is None:
            return True
        # SQLite drops tzinfo on round-trip even though fetched_at is stored
        # timezone-aware (UTC) — re-attach it before comparing.
        latest_fetched_at = latest_fetched_at.replace(tzinfo=timezone.utc)
        return latest_fetched_at < datetime.now(timezone.utc) - _STALE_AFTER

    @staticmethod
    def fetch_sheet_csv() -> str:
        """Fetch the "Current Active A-Z" worksheet as CSV.

        The sheet is currently public, so this is a plain unauthenticated
        request to its CSV export URL. If the sheet becomes restricted, this
        is the only function that needs to change (e.g. to an authenticated
        Google Sheets API v4 call with a service account).
        """
        url = _SHEET_EXPORT_URL.format(
            sheet_id=settings.feature_bin_sheet_id, gid=settings.feature_bin_sheet_gid
        )
        response = httpx.get(url, timeout=30.0, follow_redirects=True)
        response.raise_for_status()
        return response.text

    @staticmethod
    def parse_rows(csv_text: str) -> list[dict]:
        """Parse the sheet's CSV into row dicts keyed by FeatureBinRelease field names.

        Row 0 is a grouping header, row 1 has the actual column names — both
        are skipped. Every value is trimmed of leading/trailing whitespace.
        """
        rows = list(csv.reader(io.StringIO(csv_text)))
        if len(rows) < 2:
            return []

        header = [h.strip() for h in rows[1]]
        parsed: list[dict] = []
        for raw_row in rows[2:]:
            row = dict(zip(header, raw_row))
            values = {
                field_name: (row.get(col_name) or "").strip()
                for col_name, field_name in _COLUMN_MAP.items()
            }
            if not values["artist"] and not values["album"]:
                continue
            values["artist"] = transform_artist(values["artist"])
            parsed.append(values)
        return parsed

    @staticmethod
    def sync_feature_bin(db: Session, trigger: str = "scheduled") -> int:
        """Fetch the sheet and replace FeatureBinRelease with its current contents.

        No-ops (without logging a JobLog run) when the sheet isn't configured.
        """
        if not FeatureBinService.is_configured():
            logger.warning(
                "FEATURE_BIN_SHEET_ID/FEATURE_BIN_SHEET_GID not configured, skipping"
                " feature bin sync"
            )
            return 0

        csv_text = FeatureBinService.fetch_sheet_csv()
        rows = FeatureBinService.parse_rows(csv_text)

        db.query(FeatureBinRelease).delete()
        db.add_all([FeatureBinRelease(**row) for row in rows])
        db.add(JobLog(job_id="feature_bin_sync", trigger=trigger))
        db.commit()

        logger.info("Feature bin sync stored %d release(s)", len(rows))
        return len(rows)

    @staticmethod
    def build_index(db: Session) -> FeatureBinIndex:
        """Load all feature-bin releases once, for matching against many shows."""
        return FeatureBinIndex(releases=db.query(FeatureBinRelease).all())

    @staticmethod
    def find_matches(index: FeatureBinIndex, show) -> list[FeatureBinRelease]:
        """Return feature-bin releases matching a show's tagged artists or event name.

        Tagged artists (show.bands) are preferred when present; otherwise falls
        back to fuzzy-matching the whole event_name against feature-bin artists.
        """
        if not index.releases:
            return []

        band_names = [b.band_name for b in show.bands or [] if b.band_name]
        if band_names:
            matched: list[FeatureBinRelease] = []
            matched_ids: set[int] = set()
            for band_name in band_names:
                for release in index.releases:
                    if release.id in matched_ids:
                        continue
                    score = fuzz.ratio(band_name, release.artist, processor=default_process)
                    if score >= _BAND_MATCH_THRESHOLD:
                        matched.append(release)
                        matched_ids.add(release.id)
            return matched

        if not show.event_name:
            return []
        choices = {release.id: release.artist for release in index.releases}
        results = process.extract(
            show.event_name,
            choices,
            # token_set_ratio (not token_sort_ratio) since event names typically
            # have extra words around the artist name — supporting acts, "w/",
            # venue framing — that token_sort_ratio's full-string comparison
            # would otherwise penalize heavily.
            scorer=fuzz.token_set_ratio,
            processor=default_process,
            score_cutoff=_EVENT_NAME_MATCH_THRESHOLD,
            limit=None,
        )
        matched_ids = {release_id for _artist, _score, release_id in results}
        return [r for r in index.releases if r.id in matched_ids]
