"""Copy aired Spinitron playlists for the Sublist DJ shift requirement."""

import logging
from datetime import datetime, time, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.common.services.leave_service import today_pt
from app.common.services.spinitron_service import SpinitronService
from app.config import settings
from app.directory.services.eligibility import PACIFIC, add_months, quarter_start
from app.models.dj_shift_playlist import DjShiftPlaylist
from app.models.job_log import JobLog

logger = logging.getLogger(__name__)

JOB_ID = "dj_shift_sync"


def window_start(today=None) -> datetime:
    """The start of the previous quarter, Pacific midnight, as a UTC datetime."""
    start = add_months(quarter_start(today or today_pt()), -3)
    return datetime.combine(start, time.min, tzinfo=PACIFIC).astimezone(timezone.utc)


async def sync_shift_playlists(db: Session, trigger: str = "scheduled") -> Optional[int]:
    """
    Replace the stored playlists with the previous and current quarter's.

    Playlists older than the previous quarter are removed.

    :param db: Database session.
    :param trigger: "manual" or "scheduled", recorded on the JobLog entry.
    :returns: How many playlists were stored, or None if Spinitron isn't
        configured.
    :raises RuntimeError: If the Spinitron API returns an error.
    """
    if not settings.spinitron_api_key:
        logger.warning("SPINITRON_API_KEY not configured, skipping DJ shift sync")
        return None
    start = window_start()
    now = datetime.now(timezone.utc)
    playlists = await SpinitronService.fetch_playlists(start, now)
    db.query(DjShiftPlaylist).delete()
    seen = set()
    for item in playlists:
        if item["id"] in seen:
            continue
        seen.add(item["id"])
        db.add(
            DjShiftPlaylist(
                id=item["id"],
                persona_id=item["persona_id"],
                show_id=item.get("show_id"),
                start=item["start"],
                end=item["end"],
                title=item["title"],
                automation=item.get("automation", False),
                fetched_at=now,
            )
        )
    db.add(JobLog(job_id=JOB_ID, trigger=trigger))
    db.commit()
    logger.info("Stored %d Spinitron playlist(s) for DJ shifts", len(seen))
    return len(seen)


def last_synced_at(db: Session) -> Optional[datetime]:
    """When the playlists were last copied, or None if they never have been."""
    entry = (
        db.query(JobLog)
        .filter(JobLog.job_id == JOB_ID)
        .order_by(JobLog.ran_at.desc())
        .first()
    )
    if entry is None:
        return None
    ran_at = entry.ran_at
    return ran_at if ran_at.tzinfo else ran_at.replace(tzinfo=timezone.utc)
