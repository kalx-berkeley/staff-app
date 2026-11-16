"""Who is on air right now: the on-air identity the DJ pages credit.

Decisions 20–26 of docs/pass-giveaway/specs/spinitron-identity/plan.md.

A schedule slot (a cached Spinitron playlist or show) is someone when:

- its Spinitron show belongs to a Talk & Info Show: that show;
- its Spinitron show belongs to a Specialty Music Show: that show, together
  with the slot's persona (giveaways credit both);
- otherwise its persona, unless the slot aired as automation, has a title that
  never names a DJ (`SPINITRON_NON_DJ_SHOW_TITLES`, such as FREEFORM), or its
  persona is a placeholder (`SPINITRON_PLACEHOLDER_PERSONA_IDS`). Then it is
  no one.

Only a playlist's own persona counts; co-hosts listed on a Spinitron show are
ignored (decision 20).

Which slot is on air (decision 24):

1. Among playlists airing now, the one with the most recent spin wins. A
   playlist counts as airing from 10 minutes before its start (a DJ starting
   early) and, if it logged a spin after its end, for up to 15 minutes after
   it (a DJ running over).
2. Otherwise, the slot the latest schedule sync has on now, preferring a
   playlist over a show (Spinitron's `/shows` often lists a placeholder where
   `/playlists` already has the DJ's pre-provisioned playlist).

Spins come from `SpinMatchService.recent_spins`, which the DJ pages' polling
refreshes once a minute, so telling who is on air costs no extra Spinitron
calls (decision 23). A spin in a playlist the schedule cache doesn't have
costs one `/playlists/{id}` call, after which the playlist is cached.

The server decides the credit. The page can only ask to switch early to the
next slot, which is allowed in the last 10 minutes before it starts, and
only when that slot is someone (decisions 25 and 26).
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable, Literal, Optional, Union

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.common.services.spinitron_personas import persona_names
from app.common.services.spinitron_service import SpinitronService, placeholder_persona_ids
from app.database import get_db
from app.models.specialty_show import SpecialtyShow
from app.models.spinitron_playlist import SpinitronPlaylist
from app.models.spinitron_show import SpinitronShow
from app.pass_giveaway.services.spin_match_service import SpinMatchService
from app.pass_giveaway.services.specialty_show_spinitron import shows_by_spinitron_id
from app.pass_giveaway.services.spinitron_schedule_service import SpinitronScheduleService

logger = logging.getLogger(__name__)

# How long before the next slot the DJ page may switch to it (decision 25)
EARLY_SWITCH_WINDOW = timedelta(minutes=10)
# How long a playlist that logged a spin after its end keeps the identity
RUN_OVER_WINDOW = timedelta(minutes=15)
# How early a playlist's spins count, for a DJ who starts before their slot
EARLY_START_WINDOW = timedelta(minutes=10)

IdentityKind = Literal["persona", "music", "talk"]
_Row = Union[SpinitronPlaylist, SpinitronShow]


@dataclass(frozen=True)
class OnAirIdentity:
    """Who a giveaway is credited to: a persona, or a show (with a music show's DJ)."""

    kind: IdentityKind
    # The show's name, or the persona's
    name: str
    # The persona: a regular shift's DJ, or a music show slot's DJ (None if
    # the slot's persona is a placeholder). Always None for a talk show.
    persona_id: Optional[int] = None
    persona_name: Optional[str] = None
    specialty_show_id: Optional[int] = None


@dataclass
class Slot:
    """One schedule slot and who it is."""

    start: datetime
    end: datetime
    identity: Optional[OnAirIdentity]
    # The cached row's DJ name, for the DJ pages until they show identities
    dj_name: Optional[str] = None
    playlist_id: Optional[int] = None


@dataclass
class OnAir:
    """Who is on air now, and who is next."""

    current: Optional[Slot]
    next: Optional[Slot]
    # Whether `current` was decided by spins (rule 1) rather than the schedule
    from_spins: bool = False

    @property
    def identity(self) -> Optional[OnAirIdentity]:
        return self.current.identity if self.current else None

    def can_switch_early(self, now: datetime) -> bool:
        """Whether the page may offer switching to the next slot now (decision 25)."""
        nxt = self.next
        return (
            nxt is not None
            and nxt.identity is not None
            and nxt.identity != self.identity
            and now < _utc(nxt.start) <= now + EARLY_SWITCH_WINDOW
        )

    def credited(
        self, switch_to: Optional[datetime], now: datetime
    ) -> Optional[OnAirIdentity]:
        """
        Who a giveaway made now is credited to (decision 26).

        :param switch_to: The start of the slot the page switched to early,
            if it did. Honoured only while that is the next slot and it starts
            within 10 minutes; otherwise ignored.
        """
        if (
            switch_to is not None
            and self.can_switch_early(now)
            and abs(_utc(self.next.start) - _utc(switch_to)) < timedelta(seconds=1)
        ):
            return self.next.identity
        return self.identity


def _utc(dt: datetime) -> datetime:
    """SQLite drops tzinfo on round-trip even though values are stored as UTC."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


class _Resolver:
    """Turns cached schedule rows into slots with identities."""

    def __init__(self, db: Session, rows: Iterable[_Row]) -> None:
        rows = list(rows)
        self.shows: dict[int, SpecialtyShow] = shows_by_spinitron_id(db)
        self.placeholders = placeholder_persona_ids()
        self.names = persona_names(db, {r.persona_id for r in rows if r.persona_id})

    def _persona_name(self, row: _Row) -> str:
        return (
            self.names.get(row.persona_id)
            or (row.dj_name or "").strip()
            or f"Persona #{row.persona_id}"
        )

    def identity(self, row: _Row) -> Optional[OnAirIdentity]:
        if isinstance(row, SpinitronPlaylist):
            if row.automation:
                return None
            spinitron_show_id = row.show_id
        else:
            spinitron_show_id = row.id
        has_persona = row.persona_id is not None and row.persona_id not in self.placeholders
        show = self.shows.get(spinitron_show_id) if spinitron_show_id else None
        if show is not None:
            if show.is_talk:
                return OnAirIdentity(kind="talk", name=show.name, specialty_show_id=show.id)
            return OnAirIdentity(
                kind="music",
                name=show.name,
                specialty_show_id=show.id,
                persona_id=row.persona_id if has_persona else None,
                persona_name=self._persona_name(row) if has_persona else None,
            )
        if not has_persona or SpinitronScheduleService.is_non_dj_show_title(row.title):
            return None
        name = self._persona_name(row)
        return OnAirIdentity(
            kind="persona", name=name, persona_id=row.persona_id, persona_name=name
        )

    def slot(self, row: Optional[_Row]) -> Optional[Slot]:
        if row is None:
            return None
        return Slot(
            start=_utc(row.start),
            end=_utc(row.end),
            identity=self.identity(row),
            dj_name=row.dj_name,
            playlist_id=row.id if isinstance(row, SpinitronPlaylist) else None,
        )


async def _spins(db: Session) -> list[tuple[datetime, int]]:
    """Recent spins as (start, playlist ID), or none if Spinitron can't be read."""
    try:
        spins = await SpinMatchService.recent_spins(db)
    except Exception as e:  # noqa: BLE001 - fall back to the schedule
        logger.warning("Couldn't read recent spins, using the schedule: %s", e)
        db.rollback()
        return []
    found = []
    for spin in spins:
        if spin.get("playlist_id") is None or not spin.get("start"):
            continue
        found.append(
            (_utc(datetime.fromisoformat(spin["start"])), int(spin["playlist_id"]))
        )
    return found


async def _cache_unknown_playlists(db: Session, playlist_ids: set[int]) -> None:
    """Fetch and cache playlists that spins name but the schedule cache lacks."""
    known = {
        pid
        for (pid,) in db.query(SpinitronPlaylist.id).filter(
            SpinitronPlaylist.id.in_(playlist_ids)
        )
    }
    for playlist_id in sorted(playlist_ids - known):
        try:
            item = await SpinitronService.fetch_playlist(playlist_id)
        except RuntimeError as e:
            logger.warning("Couldn't fetch Spinitron playlist %s: %s", playlist_id, e)
            continue
        if not item or not item.get("start") or not item.get("end"):
            continue
        db.add(
            SpinitronPlaylist(
                id=playlist_id,
                start=datetime.strptime(item["start"], "%Y-%m-%dT%H:%M:%S%z"),
                end=datetime.strptime(item["end"], "%Y-%m-%dT%H:%M:%S%z"),
                persona_id=SpinitronService.extract_persona_id(item),
                show_id=int(item["show_id"]) if item.get("show_id") is not None else None,
                title=(item.get("title") or "").strip() or None,
                automation=bool(item.get("automation")),
            )
        )
    db.commit()


def _earliest_preferring_playlist(
    playlist: Optional[SpinitronPlaylist], show: Optional[SpinitronShow]
) -> Optional[_Row]:
    """Pick whichever entry starts first; prefer the playlist on an exact tie."""
    if playlist is None:
        return show
    if show is None:
        return playlist
    return playlist if _utc(playlist.start) <= _utc(show.start) else show


async def on_air(db: Session, now: Optional[datetime] = None) -> OnAir:
    """
    Who is on air at *now* (default: the current time), and who is next.

    :param db: Database session.
    :param now: The time to look at, for tests.
    """
    now = now or datetime.now(timezone.utc)
    spins = await _spins(db)
    if spins:
        await _cache_unknown_playlists(db, {pid for _, pid in spins})

    last_spin: dict[int, datetime] = {}
    for start, playlist_id in spins:
        if start <= now and start > last_spin.get(playlist_id, start - timedelta(1)):
            last_spin[playlist_id] = start

    playlists = (
        db.query(SpinitronPlaylist)
        .filter(SpinitronPlaylist.end > now - RUN_OVER_WINDOW)
        .order_by(SpinitronPlaylist.start)
        .all()
    )
    shows = (
        db.query(SpinitronShow)
        .filter(SpinitronShow.end > now)
        .order_by(SpinitronShow.start)
        .all()
    )
    resolver = _Resolver(db, playlists + shows)

    # Rule 1: the airing playlist with the most recent spin
    def airing(p: SpinitronPlaylist) -> bool:
        start, end = _utc(p.start), _utc(p.end)
        if start - EARLY_START_WINDOW <= now < end:
            return True
        return end <= now < end + RUN_OVER_WINDOW and last_spin[p.id] >= end

    spun = [p for p in playlists if p.id in last_spin and airing(p)]
    winner = max(spun, key=lambda p: last_spin[p.id]) if spun else None

    # Rule 2: what the schedule has on now
    scheduled: Optional[_Row] = next(
        (p for p in reversed(playlists) if _utc(p.start) <= now < _utc(p.end)), None
    ) or next((s for s in reversed(shows) if _utc(s.start) <= now < _utc(s.end)), None)

    current = winner or scheduled
    boundary = max([_utc(r.end) for r in (winner, scheduled) if r is not None] or [now])
    next_playlist = next((p for p in playlists if _utc(p.start) >= boundary), None)
    next_show = next((s for s in shows if _utc(s.start) >= boundary), None)
    return OnAir(
        current=resolver.slot(current),
        # After an early starter's playlist, not the slot they took over
        next=resolver.slot(_earliest_preferring_playlist(next_playlist, next_show)),
        from_spins=winner is not None,
    )


# The header a DJ page sends after "switch now": the start of the slot it
# switched to, as an ISO 8601 time (decision 25)
SWITCH_HEADER = "X-DJ-Switch-To"


def _parse_switch(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return _utc(datetime.fromisoformat(value.replace("Z", "+00:00")))
    except ValueError:
        return None


async def dj_identity(
    x_dj_switch_to: Optional[str] = Header(None, alias=SWITCH_HEADER),
    db: Session = Depends(get_db),
) -> Optional[OnAirIdentity]:
    """
    A dependency: who a DJ page action now is credited to, or None for no one.

    The server decides from the schedule and recent spins. The page can only
    say it switched early to the next slot, which counts only in the last 10
    minutes before that slot (decision 26).
    """
    now = datetime.now(timezone.utc)
    state = await on_air(db, now)
    return state.credited(_parse_switch(x_dj_switch_to), now)


def credit(identity: Optional[OnAirIdentity]) -> tuple[Optional[int], Optional[int]]:
    """*identity* as the (persona ID, specialty show ID) a record stores."""
    if identity is None:
        return None, None
    return identity.persona_id, identity.specialty_show_id


def identity_label(identity: Optional[OnAirIdentity]) -> str:
    """
    The name a record credited to *identity* keeps in its old DJ name text
    column until phase 4 drops it: the show's or persona's name, which the
    clean-up report still matches. Empty for no one.
    """
    return identity.name if identity is not None else ""
