"""Spinitron persona names and last playlist dates, kept in `spinitron_personas`.

A nightly job (`sync_personas`) copies Spinitron's persona directory into the
`spinitron_personas` table, and looks up when each staff member's personas
last had a playlist. Every sub-site reads persona names from here
(`persona_names`), and the persona pickers use `offered_personas` to hide a
staff member's personas that haven't been on air in six months.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from app.common.services.spinitron_service import SpinitronService
from app.config import settings
from app.models.job_log import JobLog
from app.models.spinitron_persona import SpinitronPersona
from app.models.staff import Staff

logger = logging.getLogger(__name__)

JOB_ID = "spinitron_persona_sync"

# A persona with no playlist in this long counts as inactive in the pickers
INACTIVE_AFTER = timedelta(days=183)

# How many last-playlist lookups run at once
_LOOKUP_CONCURRENCY = 5


def staff_personas(staff: Staff) -> list[dict]:
    """
    A staff member's personas, as [{"id": persona ID, "name": name}].

    Read from `Staff.dj_personas`, which the Airtable sync fills from
    Spinitron.
    """
    return [
        {"id": int(p["id"]), "name": p["name"]}
        for p in staff.dj_personas or []
        if p.get("id") is not None and p.get("name")
    ]


def staff_persona_ids(staff: Staff) -> set[int]:
    """The persona IDs linked to *staff* (Airtable's "DJ Name" links)."""
    ids = {int(i) for i in staff.spinitron_ids or []}
    ids.update(p["id"] for p in staff_personas(staff))
    return ids


async def sync_personas(db: Session, trigger: str = "scheduled") -> Optional[dict]:
    """
    Refresh `spinitron_personas` from Spinitron.

    Every persona in Spinitron's directory gets its current name. Each
    persona linked to a staff member also gets `last_playlist_at`, one
    `/playlists` call per persona. Personas Spinitron no longer lists are
    kept, so old records can still show a name.

    :param db: Database session.
    :param trigger: "manual" or "scheduled", recorded on the JobLog entry.
    :returns: {"personas": names stored, "looked_up": last playlists looked
        up, "errors": failed lookups}, or None if Spinitron isn't configured.
    :raises RuntimeError: If Spinitron's persona directory can't be read.
    """
    if not settings.spinitron_api_key:
        logger.warning("SPINITRON_API_KEY not configured, skipping persona sync")
        return None
    names = await SpinitronService.fetch_all_personas()
    if not names:
        raise RuntimeError("Spinitron returned no personas")

    staff_ids: set[int] = set()
    for staff in db.query(Staff).filter(
        (Staff.spinitron_ids.isnot(None)) | (Staff.dj_personas.isnot(None))
    ):
        staff_ids |= staff_persona_ids(staff)

    semaphore = asyncio.Semaphore(_LOOKUP_CONCURRENCY)
    errors = 0

    async def lookup(persona_id: int) -> tuple[int, Optional[datetime], bool]:
        async with semaphore:
            try:
                start = await SpinitronService.fetch_last_playlist_start(persona_id)
                return persona_id, start, True
            except RuntimeError as e:
                logger.warning(
                    "Last playlist lookup failed for persona %s: %s", persona_id, e
                )
                return persona_id, None, False

    results = await asyncio.gather(*(lookup(pid) for pid in sorted(staff_ids)))

    existing = {p.id: p for p in db.query(SpinitronPersona).all()}
    now = datetime.now(timezone.utc)
    for persona_id, name in names.items():
        row = existing.get(persona_id)
        if row is None:
            row = SpinitronPersona(id=persona_id, name=name, updated_at=now)
            db.add(row)
            existing[persona_id] = row
        elif row.name != name:
            row.name = name
    for persona_id, start, ok in results:
        if not ok:
            errors += 1
            continue
        row = existing.get(persona_id)
        if row is None:
            # A staff member's persona that the directory left out
            continue
        row.last_playlist_at = start
    db.add(JobLog(job_id=JOB_ID, trigger=trigger))
    db.commit()
    logger.info(
        "Stored %d Spinitron personas; looked up %d last playlists (%d failed)",
        len(names),
        len(results),
        errors,
    )
    return {"personas": len(names), "looked_up": len(results) - errors, "errors": errors}


def persona_names(db: Session, persona_ids: Iterable[int]) -> dict[int, str]:
    """
    The current names of *persona_ids*.

    Read from `spinitron_personas`, falling back to staff records for a
    persona the nightly sync hasn't stored yet. IDs with no known name are
    left out.
    """
    wanted = {int(i) for i in persona_ids if i is not None}
    if not wanted:
        return {}
    names = {
        pid: name
        for pid, name in db.query(SpinitronPersona.id, SpinitronPersona.name).filter(
            SpinitronPersona.id.in_(wanted)
        )
    }
    missing = wanted - names.keys()
    if missing:
        for (rows,) in db.query(Staff.dj_personas).filter(Staff.dj_personas.isnot(None)):
            for persona in rows or []:
                pid = persona.get("id")
                if pid is not None and int(pid) in missing and persona.get("name"):
                    names.setdefault(int(pid), persona["name"])
    return names


def _aware(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None or dt.tzinfo is not None:
        return dt
    return dt.replace(tzinfo=timezone.utc)


def offered_personas(
    db: Session,
    personas: list[dict],
    keep_ids: Iterable[int] = (),
    now: Optional[datetime] = None,
) -> list[dict]:
    """
    One staff member's personas that a picker should offer.

    When they have several personas and at least one had a playlist in the
    last six months, the ones that didn't are left out. Otherwise all are
    offered. Personas in *keep_ids* (already assigned) are always offered.

    :param db: Database session.
    :param personas: The staff member's personas, from `staff_personas`.
    :param keep_ids: Persona IDs to offer whatever their last playlist.
    :param now: The current time, for tests.
    :returns: The offered personas, in the order given, each with its current
        name (from `persona_names`).
    """
    if not personas:
        return []
    ids = [p["id"] for p in personas]
    names = persona_names(db, ids)
    personas = [{**p, "name": names.get(p["id"], p["name"])} for p in personas]
    if len(personas) == 1:
        return personas
    cutoff = (now or datetime.now(timezone.utc)) - INACTIVE_AFTER
    last = {
        pid: _aware(at)
        for pid, at in db.query(
            SpinitronPersona.id, SpinitronPersona.last_playlist_at
        ).filter(SpinitronPersona.id.in_(ids))
    }
    active = {pid for pid in ids if last.get(pid) is not None and last[pid] >= cutoff}
    if not active:
        return personas
    keep = {int(i) for i in keep_ids}
    return [p for p in personas if p["id"] in active or p["id"] in keep]
