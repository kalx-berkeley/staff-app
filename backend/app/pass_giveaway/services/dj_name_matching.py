"""Match DJ names typed as text to Spinitron personas and shows.

Until the pass giveaway moved to Spinitron personas, DJ names were stored as
free text in several tables (`NAME_COLUMNS`). This works out what each name
refers to, for `scripts/spinitron_identity_report.py` (which finds the names
that need fixing by hand) and for the migration that fills in persona and
show IDs.

Names are compared normalized (`tracking_service.normalize_dj_name`:
lowercase, whitespace collapsed). A name matches, in order:

1. its `DjNameMapping`, if someone made one;
2. for a row that already has a specialty show ID, that show;
3. a Specialty Music Show or Talk & Info Show of that name (not deleted),
   where a show is allowed;
4. a Spinitron persona of that name. When several personas share it, the one
   linked to a staff member, if exactly one is.

A name matching both a show and a persona, or several personas none or more
than one of which is a staff member's, is ambiguous and needs a mapping.
"""

from __future__ import annotations

import difflib
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from app.common.services.tracking_service import normalize_dj_name
from app.models.analytics_event import AnalyticsDailyCount, AnalyticsEvent
from app.models.dj_name_mapping import DjNameMapping
from app.models.lottery_entry import LotteryEntry
from app.models.on_air_winner import OnAirWinner
from app.models.pass_model import Pass
from app.models.show_attempt import ShowAttempt
from app.models.specialty_show import SpecialtyShow
from app.models.specialty_show_dj import SpecialtyShowDJ
from app.models.spinitron_playlist import SpinitronPlaylist
from app.models.spinitron_show import SpinitronShow
from app.models.staff import Staff


@dataclass(frozen=True)
class NameColumn:
    """A text column holding DJ names."""

    # e.g. "passes.given_away_by_dj"
    label: str
    model: type
    column: str
    # A column on the same row that, when set, already says which show it is
    show_id_column: Optional[str] = None
    # Whether the name may be a show's rather than a persona's
    allow_show: bool = True


NAME_COLUMNS: list[NameColumn] = [
    NameColumn(
        "passes.preassigned_dj", Pass, "preassigned_dj", "preassigned_specialty_show_id"
    ),
    NameColumn("passes.given_away_by_dj", Pass, "given_away_by_dj"),
    NameColumn("on_air_winners.given_away_by_dj", OnAirWinner, "given_away_by_dj"),
    NameColumn("show_attempts.dj_name", ShowAttempt, "dj_name"),
    NameColumn("lottery_entries.dj_name", LotteryEntry, "dj_name", "specialty_show_id"),
    NameColumn("specialty_show_djs.dj_name", SpecialtyShowDJ, "dj_name", allow_show=False),
    NameColumn("analytics_event.dj_name", AnalyticsEvent, "dj_name"),
    NameColumn("analytics_daily_count.dj_name", AnalyticsDailyCount, "dj_name"),
]

# Match kinds
PERSONA = "persona"
SHOW = "show"
UNATTRIBUTED = "unattributed"
AMBIGUOUS = "ambiguous"
UNMATCHED = "unmatched"


@dataclass
class Match:
    """What a name refers to."""

    kind: str
    persona_id: Optional[int] = None
    specialty_show_id: Optional[int] = None
    # Why a name is ambiguous or unmatched, for the report
    reason: str = ""

    @property
    def resolved(self) -> bool:
        """True when the name needs no fixing."""
        return self.kind in (PERSONA, SHOW, UNATTRIBUTED)


@dataclass
class NameDirectory:
    """Everything a name can match, keyed by normalized name."""

    # Persona ID -> name, from Spinitron, staff records and the schedule cache
    persona_names: dict[int, str]
    # Persona IDs linked to a staff member (any status)
    staff_persona_ids: set[int]
    # Normalized name -> show ID, for shows that aren't deleted
    shows: dict[str, int]
    # Show ID -> (name, category), for shows that aren't deleted
    show_info: dict[int, tuple[str, str]]
    mappings: dict[str, DjNameMapping]
    personas_by_key: dict[str, set[int]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        by_key: dict[str, set[int]] = defaultdict(set)
        for persona_id, name in self.persona_names.items():
            key = normalize_dj_name(name)
            if key:
                by_key[key].add(persona_id)
        self.personas_by_key = dict(by_key)

    def match(self, name: Optional[str], allow_show: bool = True) -> Match:
        """
        What *name* refers to.

        :param name: The name as stored.
        :param allow_show: Whether the name may be a show's.
        :returns: The match; `UNATTRIBUTED` for a blank name.
        """
        key = normalize_dj_name(name)
        if key is None:
            return Match(UNATTRIBUTED, reason="blank")
        mapping = self.mappings.get(key)
        if mapping is not None:
            if mapping.specialty_show_id is not None:
                if not allow_show:
                    return Match(
                        UNMATCHED,
                        reason="mapped to a show, but this column needs a persona",
                    )
                return Match(SHOW, specialty_show_id=mapping.specialty_show_id)
            if mapping.persona_id is not None:
                return Match(PERSONA, persona_id=mapping.persona_id)
            return Match(UNATTRIBUTED, reason="mapped to no one")

        show_id = self.shows.get(key) if allow_show else None
        persona_ids = self.personas_by_key.get(key, set())
        if persona_ids and len(persona_ids) > 1:
            staff_ids = persona_ids & self.staff_persona_ids
            persona_id = next(iter(staff_ids)) if len(staff_ids) == 1 else None
        else:
            persona_id = next(iter(persona_ids), None)

        if show_id is not None and persona_ids:
            return Match(
                AMBIGUOUS,
                reason=(
                    f"a show ({self.show_info[show_id][0]}, #{show_id}) and persona(s)"
                    f" {self._persona_list(persona_ids)} share this name"
                ),
            )
        if show_id is not None:
            return Match(SHOW, specialty_show_id=show_id)
        if persona_id is not None:
            return Match(PERSONA, persona_id=persona_id)
        if persona_ids:
            return Match(
                AMBIGUOUS,
                reason=(
                    f"personas {self._persona_list(persona_ids)} share this name, and"
                    " not exactly one of them is a staff member's"
                ),
            )
        return Match(UNMATCHED, reason="no persona or show has this name")

    def suggestions(self, name: str, limit: int = 3) -> list[str]:
        """Persona and show names close to *name*, for spotting typos."""
        key = normalize_dj_name(name) or ""
        candidates = {normalize_dj_name(n): n for n in self.persona_names.values()}
        candidates.update({k: self.show_info[v][0] for k, v in self.shows.items()})
        close = difflib.get_close_matches(key, list(candidates), n=limit, cutoff=0.8)
        return [candidates[c] for c in close]

    def _persona_list(self, persona_ids: Iterable[int]) -> str:
        return ", ".join(
            f"#{pid}{' (staff)' if pid in self.staff_persona_ids else ''}"
            for pid in sorted(persona_ids)
        )


def build_directory(db: Session, spinitron_personas: dict[int, str]) -> NameDirectory:
    """
    Gather every persona, show and mapping a name can match.

    :param db: Database session.
    :param spinitron_personas: Spinitron's persona directory (ID -> name);
        may be empty when Spinitron can't be reached, leaving only the
        personas known from staff records and the schedule cache.
    :returns: The directory.
    """
    persona_names: dict[int, str] = {}
    staff_persona_ids: set[int] = set()
    for (rows,) in db.query(Staff.dj_personas).filter(Staff.dj_personas.isnot(None)):
        for persona in rows or []:
            persona_names[int(persona["id"])] = persona["name"]
            staff_persona_ids.add(int(persona["id"]))
    for (ids,) in db.query(Staff.spinitron_ids).filter(Staff.spinitron_ids.isnot(None)):
        staff_persona_ids.update(int(i) for i in ids or [])
    for model in (SpinitronShow, SpinitronPlaylist):
        for persona_id, name in db.query(model.persona_id, model.dj_name).filter(
            model.persona_id.isnot(None), model.dj_name.isnot(None)
        ):
            persona_names.setdefault(int(persona_id), name)
    # Spinitron's own names win over cached ones
    persona_names.update(spinitron_personas)

    shows: dict[str, int] = {}
    show_info: dict[int, tuple[str, str]] = {}
    for show in db.query(SpecialtyShow).filter(SpecialtyShow.deleted.is_(False)):
        show_info[show.id] = (show.name, show.category)
        key = normalize_dj_name(show.name)
        if key:
            shows[key] = show.id

    mappings = {m.name_key: m for m in db.query(DjNameMapping).all()}
    return NameDirectory(persona_names, staff_persona_ids, shows, show_info, mappings)


@dataclass
class NameUse:
    """One distinct name in one column, with what it matched."""

    column: NameColumn
    name: str
    rows: int
    match: Match


def name_uses(db: Session, directory: NameDirectory) -> list[NameUse]:
    """
    Every distinct name in every DJ name column, with its row count and match.

    Rows whose show ID column is set count as matched to that show, whatever
    their text says. Blank names are left out.

    :param db: Database session.
    :param directory: From `build_directory`.
    :returns: One entry per (column, name as stored, show ID) combination.
    """
    from sqlalchemy import func

    uses: list[NameUse] = []
    for col in NAME_COLUMNS:
        text = getattr(col.model, col.column)
        show_col = getattr(col.model, col.show_id_column) if col.show_id_column else None
        count = (
            func.sum(col.model.count) if col.model is AnalyticsDailyCount else func.count()
        )
        group = [text] + ([show_col] if show_col is not None else [])
        query = db.query(*group, count).filter(text.isnot(None)).group_by(*group)
        for row in query:
            name, rows = row[0], int(row[-1])
            show_id = row[1] if show_col is not None else None
            if not normalize_dj_name(name):
                continue
            if show_id is not None:
                match = Match(SHOW, specialty_show_id=show_id)
            else:
                match = directory.match(name, allow_show=col.allow_show)
            uses.append(NameUse(col, name, rows, match))
    return uses


# Columns that store names normalized, so a fix writes the normalized name
_NORMALIZED_MODELS = (AnalyticsEvent, AnalyticsDailyCount)
# The unique key of a daily count, apart from its DJ name
_DAILY_COUNT_KEY = (
    "day",
    "event_type",
    "area",
    "actor_email",
    "network",
    "entity_type",
    "entity_id",
    "dimension",
)


def column_by_label(label: str) -> Optional[NameColumn]:
    """
    Find a `NAME_COLUMNS` entry by its label, e.g. "passes.given_away_by_dj".

    :param label: The label.
    :returns: The column, or None.
    """
    return next((c for c in NAME_COLUMNS if c.label == label), None)


def fix_name(
    db: Session,
    old: str,
    new: str,
    columns: Optional[Iterable[NameColumn]] = None,
    show_id: Optional[int] = None,
) -> dict[str, int]:
    """
    Change a DJ name stored as text, in place, without committing.

    Rows match *old* compared normalized, so "dj fooo" also changes "DJ Fooo".
    Columns that store names normalized (analytics) get *new* normalized. A
    daily count that would then duplicate another day's count for *new* is
    added to it and removed.

    :param db: Database session. The caller commits or rolls back.
    :param old: The name to change.
    :param new: What to change it to.
    :param columns: Only these columns; every one in `NAME_COLUMNS` when None.
    :param show_id: Only rows for this pass giveaway show. Columns without a
        show (music show DJs, analytics) are then left alone.
    :returns: Rows changed per column label, leaving out columns with none.
    :raises ValueError: When either name is blank.
    """
    old_key = normalize_dj_name(old)
    new_text = " ".join(new.split())
    if not old_key or not new_text:
        raise ValueError("Names can't be blank")

    changed: dict[str, int] = {}
    for col in columns if columns is not None else NAME_COLUMNS:
        model = col.model
        if show_id is not None and not hasattr(model, "show_id"):
            continue
        text = getattr(model, col.column)
        target = normalize_dj_name(new_text) if model in _NORMALIZED_MODELS else new_text
        query = db.query(model).filter(text.isnot(None))
        if show_id is not None:
            query = query.filter(model.show_id == show_id)
        values = [
            v
            for (v,) in query.with_entities(text).distinct()
            if normalize_dj_name(v) == old_key and v != target
        ]
        if not values:
            continue
        rows = query.filter(text.in_(values)).all()
        for row in rows:
            if model is AnalyticsDailyCount:
                twin = (
                    db.query(AnalyticsDailyCount)
                    .filter(AnalyticsDailyCount.dj_name == target)
                    .filter(*(
                        (
                            getattr(AnalyticsDailyCount, k).is_(None)
                            if getattr(row, k) is None
                            else getattr(AnalyticsDailyCount, k) == getattr(row, k)
                        )
                        for k in _DAILY_COUNT_KEY
                    ))
                    .first()
                )
                if twin is not None:
                    twin.count += row.count
                    db.delete(row)
                    continue
            setattr(row, col.column, target)
        db.flush()
        changed[col.label] = len(rows)
    return changed
