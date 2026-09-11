"""Syncs the upcoming Spinitron on-air schedule into the SpinitronShow cache table."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Set

from sqlalchemy.orm import Session

from app.config import settings
from app.models.job_log import JobLog
from app.models.spinitron_show import SpinitronShow
from app.models.staff import Staff
from app.services.spinitron_service import SpinitronService

logger = logging.getLogger(__name__)


class SpinitronScheduleService:
    """Fetches and caches the upcoming Spinitron on-air schedule."""

    @staticmethod
    async def sync_schedule(
        db: Session, trigger: str = "scheduled", hours_ahead: int = 12
    ) -> int:
        """
        Fetch the next *hours_ahead* hours of Spinitron shows and replace the cache.

        Resolves each show's first persona to a DJ name, preferring the local
        Staff directory (already resolved during the Airtable sync) over a
        Spinitron persona API call. A show whose persona is a configured
        "placeholder" (a rotating slot like "DJ Trainee" rather than a specific
        DJ) is stored with no DJ name, same as a show with no persona at all —
        this stops the DJ Name field from being auto-filled or flagged as
        mismatched during that show.

        No-ops (without logging a JobLog run) when Spinitron isn't configured.

        :param db: Database session.
        :param trigger: "manual" or "scheduled", recorded on the JobLog entry.
        :param hours_ahead: How far ahead of now to fetch the schedule.
        :returns: Number of shows cached.
        """
        if not settings.spinitron_api_key:
            logger.warning("SPINITRON_API_KEY not configured, skipping schedule sync")
            return 0

        end = datetime.now(timezone.utc) + timedelta(hours=hours_ahead)
        shows = await SpinitronService.fetch_shows(end)

        staff_persona_names = SpinitronScheduleService._single_persona_staff_names(db)
        placeholder_ids = SpinitronScheduleService._placeholder_persona_ids()
        resolved: Dict[int, Optional[str]] = {}

        rows: list[SpinitronShow] = []
        for show in shows:
            persona_id = show["persona_id"]
            dj_name = None
            if persona_id is not None and persona_id not in placeholder_ids:
                if persona_id in resolved:
                    dj_name = resolved[persona_id]
                elif persona_id in staff_persona_names:
                    dj_name = staff_persona_names[persona_id]
                    resolved[persona_id] = dj_name
                else:
                    dj_name = await SpinitronService.fetch_persona_name(persona_id)
                    resolved[persona_id] = dj_name

            rows.append(
                SpinitronShow(
                    id=show["id"],
                    start=show["start"],
                    end=show["end"],
                    dj_name=dj_name,
                    persona_id=persona_id,
                )
            )

        db.query(SpinitronShow).delete()
        db.add_all(rows)
        db.add(JobLog(job_id="spinitron_schedule_sync", trigger=trigger))
        db.commit()

        logger.info("Spinitron schedule sync cached %d show(s)", len(rows))
        return len(rows)

    @staticmethod
    def _placeholder_persona_ids() -> Set[int]:
        """Parse SPINITRON_PLACEHOLDER_PERSONA_IDS into a set of persona IDs."""
        return {
            int(raw_id.strip())
            for raw_id in settings.spinitron_placeholder_persona_ids.split(",")
            if raw_id.strip()
        }

    @staticmethod
    def _single_persona_staff_names(db: Session) -> Dict[int, str]:
        """
        Map persona ID -> DJ name for Staff records with exactly one Spinitron ID.

        `Staff.dj_name` is a comma-joined string when a staff member has
        multiple `spinitron_ids`, so it's only safe to reuse directly when
        there's a single ID — otherwise we'd attribute the joined name to one
        persona.
        """
        names: Dict[int, str] = {}
        staff = (
            db.query(Staff)
            .filter(Staff.spinitron_ids.isnot(None), Staff.dj_name.isnot(None))
            .all()
        )
        for record in staff:
            ids = record.spinitron_ids or []
            if len(ids) == 1:
                names[int(ids[0])] = record.dj_name
        return names
