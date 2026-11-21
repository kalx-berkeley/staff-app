"""
Linked callers: on-air winners' phone numbers confirmed to be one person.

A caller who gives a different phone number each time could get around a
venue's win frequency limit. Promotions admins link those numbers into one
caller (`OnAirCaller`) in Promotions → Admin, and the limit check then looks
at wins on every one of them (`linked_phones`). Suggestions come from the same
similar-name grouping as KALX Staff Analytics (`caller_names`); a suggestion
can be dismissed ("not the same person", stored as pairs of numbers) or its
name marked too common to suggest. Design:
docs/pass-giveaway/specs/linked-callers/plan.md.

Phone numbers are stored as `on_air_winners` stores them (digits only).
Comparisons go through `tracking_service.normalize_phone`, which also drops a
leading US 1, so analytics (which uses that form) agrees with this module.
"""

import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from itertools import combinations
from typing import Iterable, Optional, Protocol

from sqlalchemy.orm import Session, selectinload

from app.common.areas import PASS_GIVEAWAY_AREA
from app.common.services import audit_service
from app.common.services.tracking_service import normalize_person_name
from app.common.services.tracking_service import normalize_phone as phone_key
from app.models.on_air_caller import (
    CommonCallerName,
    DismissedCallerPair,
    OnAirCaller,
    OnAirCallerPhone,
)
from app.models.on_air_winner import OnAirWinner
from app.models.venue import Venue
from app.pass_giveaway.services.caller_names import group_similar_names, is_same_caller_name

LINKED = "linked"
PARTLY_LINKED = "partly_linked"
DISMISSED = "dismissed"
COMMON = "common"
UNREVIEWED = "unreviewed"

STATUS_LABELS = {
    LINKED: "Linked",
    PARTLY_LINKED: "Partly linked",
    DISMISSED: "Dismissed",
    COMMON: "Common name",
    UNREVIEWED: "Unreviewed",
}

# A suggestion with one of these statuses needs no more review
RESOLVED = frozenset({LINKED, DISMISSED, COMMON})

SEARCH_LIMIT = 25


def stored_phone(phone: Optional[str]) -> str:
    """A phone number as `on_air_winners` stores it: digits only."""
    return re.sub(r"\D", "", phone or "")


def linked_phones(db: Session, phone: str) -> set[str]:
    """
    The phone number plus every number linked to it, as stored.

    Args:
        db: Database session
        phone: A phone number in any format
    """
    digits = stored_phone(phone)
    row = db.query(OnAirCallerPhone).filter(OnAirCallerPhone.phone == digits).first()
    if row is None:
        return {digits}
    others = db.query(OnAirCallerPhone.phone).filter(
        OnAirCallerPhone.caller_id == row.caller_id
    )
    return {digits} | {p for (p,) in others}


def _pair(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a < b else (b, a)


@dataclass
class LinkState:
    """Every link, dismissal and common name, loaded once for grouping."""

    # phone_key(phone) → caller ID
    caller_of: dict[str, int] = field(default_factory=dict)
    # Pairs of phone_key(phone), smaller first
    dismissed: set[tuple[str, str]] = field(default_factory=set)
    common: set[str] = field(default_factory=set)

    @classmethod
    def load(cls, db: Session) -> "LinkState":
        return cls(
            caller_of={
                phone_key(p): c
                for p, c in db.query(OnAirCallerPhone.phone, OnAirCallerPhone.caller_id)
            },
            dismissed={
                _pair(phone_key(a), phone_key(b))
                for a, b in db.query(
                    DismissedCallerPair.phone_a, DismissedCallerPair.phone_b
                )
            },
            common={n for (n,) in db.query(CommonCallerName.name)},
        )

    def caller_id(self, phone: str) -> Optional[int]:
        return self.caller_of.get(phone_key(phone))

    def person_key(self, phone: str) -> str:
        """The same key for every number of one linked caller, else the number."""
        caller = self.caller_id(phone)
        return f"caller:{caller}" if caller is not None else phone_key(phone)

    def status(self, phones: Iterable[str], names: Iterable[str]) -> str:
        """
        A suggested group's status.

        Args:
            phones: The group's phone numbers
            names: The group's names, normalized
        """
        if any(n in self.common for n in names):
            return COMMON
        keys = sorted({phone_key(p) for p in phones if phone_key(p)})
        if len({self.person_key(k) for k in keys}) <= 1:
            return LINKED
        unresolved = any(
            self.person_key(a) != self.person_key(b) and (a, b) not in self.dismissed
            for a, b in combinations(keys, 2)
        )
        if not unresolved:
            return DISMISSED
        return PARTLY_LINKED if any(k in self.caller_of for k in keys) else UNREVIEWED


# ---------------------------------------------------------------------------
# Win limits, shared with the analytics


class _WinLike(Protocol):
    phone: str
    venue_id: int
    show_date: Optional[date]


def venue_win_limits(db: Session) -> dict[int, tuple[int, Optional[int]]]:
    """Venue ID → (the ID of the venue whose win limit applies, that limit)."""
    rows = db.query(Venue.id, Venue.parent_venue_id, Venue.win_frequency_days).all()
    own = {venue_id: days for venue_id, _, days in rows}
    return {
        venue_id: (parent_id, own.get(parent_id)) if parent_id else (venue_id, days)
        for venue_id, parent_id, days in rows
    }


def bypasses_win_limit(
    ws: Iterable[_WinLike], win_limits: dict[int, tuple[int, Optional[int]]]
) -> bool:
    """
    Whether two different phones won within one win limit.

    Args:
        ws: One name's wins
        win_limits: Venue ID → (the ID of the venue whose limit applies, that
            limit). Venues sharing a limit are compared as one venue.
    """
    by_family: dict[int, list[_WinLike]] = defaultdict(list)
    limits: dict[int, Optional[int]] = {}
    for w in ws:
        family_id, limit = win_limits.get(w.venue_id, (w.venue_id, None))
        by_family[family_id].append(w)
        limits[family_id] = limit
    for family_id, vws in by_family.items():
        limit = limits[family_id]
        if not limit:
            continue
        for i, a in enumerate(vws):
            for b in vws[i + 1:]:  # fmt: skip
                if (
                    a.phone != b.phone
                    and a.show_date
                    and b.show_date
                    and abs((a.show_date - b.show_date).days) < limit
                ):
                    return True
    return False


# ---------------------------------------------------------------------------
# Reading


@dataclass
class _Win:
    pass_id: int
    name: str
    normalized: str
    phone: str
    email: Optional[str]
    venue_id: int
    venue: str
    show_id: int
    show: str
    show_date: Optional[date]
    won_at: datetime


def _all_wins(db: Session) -> list[_Win]:
    """Every on-air win, oldest first."""
    q = (
        db.query(OnAirWinner)
        .options(selectinload(OnAirWinner.show), selectinload(OnAirWinner.venue))
        .order_by(OnAirWinner.created_at, OnAirWinner.id)
    )
    return [
        _Win(
            pass_id=w.pass_id,
            name=(w.recipient_name or "").strip(),
            normalized=normalize_person_name(w.recipient_name),
            phone=w.recipient_phone or "",
            email=(w.recipient_email or "").strip() or None,
            venue_id=w.venue_id,
            venue=w.venue.name if w.venue else "",
            show_id=w.show_id,
            show=w.show.event_name if w.show else "",
            show_date=w.show.show_date if w.show else None,
            won_at=w.created_at,
        )
        for w in q.all()
    ]


def _win_dict(w: _Win) -> dict:
    return {
        "pass_id": w.pass_id,
        "won_at": w.won_at,
        "name": w.name,
        "phone": w.phone,
        "email": w.email,
        "show_id": w.show_id,
        "show": w.show,
        "show_date": w.show_date,
        "venue": w.venue,
    }


def _latest_first_names(ws: list[_Win]) -> list[str]:
    """Each different spelling, latest first (ws is oldest first)."""
    seen: dict[str, str] = {}
    for w in reversed(ws):
        if w.name:
            seen.setdefault(w.normalized or w.name, w.name)
    return list(seen.values())


def _phone_summary(phone: str, ws: list[_Win], state: LinkState) -> dict:
    return {
        "phone": phone,
        "names": _latest_first_names(ws),
        "wins": len(ws),
        "last_won_at": ws[-1].won_at if ws else None,
        "caller_id": state.caller_id(phone),
    }


def suggestions(
    db: Session, include_resolved: bool = False, name: Optional[str] = None
) -> list[dict]:
    """
    Groups of similar names with two or more phone numbers.

    Args:
        db: Database session
        include_resolved: Also list linked, dismissed and common-name groups
        name: Only the group this name belongs to (resolved or not)

    Returns:
        Groups that would have broken a venue limit first, then latest win first
    """
    state = LinkState.load(db)
    wins = _all_wins(db)
    groups = group_similar_names(w.normalized for w in wins)
    by_group: dict[str, list[_Win]] = defaultdict(list)
    for w in wins:
        if w.normalized and w.phone:
            by_group[groups[w.normalized]].append(w)
    wanted = normalize_person_name(name) if name else None
    limits = venue_win_limits(db)
    out = []
    for key, ws in by_group.items():
        phones = sorted({w.phone for w in ws})
        if len({phone_key(p) for p in phones}) < 2:
            continue
        names = {w.normalized for w in ws}
        if wanted is not None and not any(is_same_caller_name(wanted, n) for n in names):
            continue
        status = state.status(phones, names)
        if status in RESOLVED and not include_resolved and wanted is None:
            continue
        by_phone: dict[str, list[_Win]] = defaultdict(list)
        for w in ws:
            by_phone[w.phone].append(w)
        out.append({
            "key": key,
            "name": ws[-1].name,
            "spellings": _latest_first_names(ws),
            "status": status,
            "status_label": STATUS_LABELS[status],
            "flagged": bypasses_win_limit(ws, limits),
            "common_names": sorted(n for n in names if n in state.common),
            "phones": [_phone_summary(p, by_phone[p], state) for p in phones],
            "wins": [_win_dict(w) for w in reversed(ws)],
        })
    out.sort(key=lambda g: (not g["flagged"], -g["wins"][0]["won_at"].timestamp()))
    return out


def callers(db: Session) -> list[dict]:
    """Every linked caller, with each number's names and wins, newest link first."""
    state = LinkState.load(db)
    by_phone: dict[str, list[_Win]] = defaultdict(list)
    for w in _all_wins(db):
        by_phone[w.phone].append(w)
    rows = (
        db.query(OnAirCaller)
        .options(selectinload(OnAirCaller.phones))
        .order_by(OnAirCaller.updated_at.desc(), OnAirCaller.id.desc())
        .all()
    )
    return [caller_dict(c, by_phone, state) for c in rows]


def caller_dict(
    caller: OnAirCaller,
    by_phone: Optional[dict[str, list[_Win]]] = None,
    state: Optional[LinkState] = None,
    db: Optional[Session] = None,
) -> dict:
    """One caller for the API. Pass *db* rather than *by_phone* and *state*."""
    if by_phone is None or state is None:
        assert db is not None
        state = LinkState.load(db)
        by_phone = defaultdict(list)
        for w in _all_wins(db):
            by_phone[w.phone].append(w)
    phones = [
        _phone_summary(p.phone, by_phone.get(p.phone, []), state) for p in caller.phones
    ]
    return {
        "id": caller.id,
        "note": caller.note,
        "created_at": caller.created_at,
        "updated_at": caller.updated_at,
        "phones": phones,
    }


def search(db: Session, q: str) -> list[dict]:
    """
    Winners' phone numbers whose number contains *q*'s digits (3 or more), or
    whose winner's name contains *q*, latest win first.
    """
    state = LinkState.load(db)
    digits = stored_phone(q)
    needle = normalize_person_name(q)
    by_phone: dict[str, list[_Win]] = defaultdict(list)
    for w in _all_wins(db):
        if w.phone:
            by_phone[w.phone].append(w)
    matches = []
    for phone, ws in by_phone.items():
        if len(digits) >= 3:
            hit = digits in phone
        else:
            hit = bool(needle) and any(needle in w.normalized for w in ws)
        if hit:
            matches.append(_phone_summary(phone, ws, state))
    matches.sort(key=lambda m: m["last_won_at"], reverse=True)
    return matches[:SEARCH_LIMIT]


# ---------------------------------------------------------------------------
# Changing


def _clean_phones(phones: Iterable[str]) -> list[str]:
    return sorted({stored_phone(p) for p in phones if stored_phone(p)})


def preview_link(db: Session, phones: Iterable[str]) -> dict:
    """
    What linking *phones* would do.

    Raises:
        ValueError: Fewer than two numbers, or a number with no wins that
            isn't already linked

    Returns:
        ``phones``: every number that would end up together, ``caller_ids``:
        the callers it would merge (or add to), ``already_linked``: whether
        they're already one caller
    """
    numbers = _clean_phones(phones)
    if len(numbers) < 2:
        raise ValueError("Pick at least two phone numbers to link")
    rows = {
        r.phone: r
        for r in db.query(OnAirCallerPhone).filter(OnAirCallerPhone.phone.in_(numbers))
    }
    won = {
        p
        for (p,) in db.query(OnAirWinner.recipient_phone).filter(
            OnAirWinner.recipient_phone.in_(numbers)
        )
    }
    unknown = [p for p in numbers if p not in won and p not in rows]
    if unknown:
        raise ValueError(f"No on-air winner has the phone number {unknown[0]}")
    caller_ids = sorted({r.caller_id for r in rows.values()})
    together = set(numbers)
    if caller_ids:
        together |= {
            p
            for (p,) in db.query(OnAirCallerPhone.phone).filter(
                OnAirCallerPhone.caller_id.in_(caller_ids)
            )
        }
    return {
        "phones": sorted(together),
        "caller_ids": caller_ids,
        "already_linked": len(caller_ids) == 1 and len(rows) == len(numbers),
    }


def link(
    db: Session, phones: Iterable[str], note: Optional[str], actor_email: str
) -> OnAirCaller:
    """
    Link phone numbers into one caller, merging any callers they're already in.

    Deletes the dismissed pairs among the resulting numbers (decision 16).

    Raises:
        ValueError: As `preview_link`, or when they're already linked
    """
    preview = preview_link(db, phones)
    if preview["already_linked"]:
        raise ValueError("These phone numbers are already linked")
    note = (note or "").strip() or None
    caller_ids = preview["caller_ids"]
    merging = db.query(OnAirCaller).filter(OnAirCaller.id.in_(caller_ids)).all()
    merging.sort(key=lambda c: c.id)
    if merging:
        caller, others = merging[0], merging[1:]
    else:
        caller, others = OnAirCaller(), []
        db.add(caller)
        db.flush()
    notes = [c.note for c in merging if c.note] + ([note] if note else [])
    caller.note = "\n".join(notes) or None
    existing = {p.phone for c in merging for p in c.phones}
    for other in others:
        for p in list(other.phones):
            p.caller_id = caller.id
        db.flush()
        db.expire(other, ["phones"])
        db.delete(other)
    added = [p for p in preview["phones"] if p not in existing]
    for p in added:
        db.add(OnAirCallerPhone(phone=p, caller_id=caller.id))
    together = set(preview["phones"])
    removed = []
    for pair in db.query(DismissedCallerPair).filter(
        DismissedCallerPair.phone_a.in_(together), DismissedCallerPair.phone_b.in_(together)
    ):
        removed.append([pair.phone_a, pair.phone_b])
        db.delete(pair)
    caller.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(caller)
    audit_service.log_event(
        db,
        event_type="callers_linked",
        area=PASS_GIVEAWAY_AREA,
        actor_email=actor_email,
        actor_role="promotions",
        entity_type="on_air_caller",
        entity_id=caller.id,
        details={
            "phones": preview["phones"],
            "added_phones": added,
            "merged_caller_ids": [c.id for c in others],
            "removed_dismissals": removed,
            "note": note,
        },
    )
    return caller


def get_caller(db: Session, caller_id: int) -> OnAirCaller:
    """
    Raises:
        LookupError: No such caller
    """
    caller = db.query(OnAirCaller).filter(OnAirCaller.id == caller_id).first()
    if caller is None:
        raise LookupError("Linked caller not found")
    return caller


def update_note(
    db: Session, caller_id: int, note: Optional[str], actor_email: str
) -> OnAirCaller:
    """Change a caller's note (blank clears it)."""
    caller = get_caller(db, caller_id)
    before = caller.note
    caller.note = (note or "").strip() or None
    db.commit()
    db.refresh(caller)
    audit_service.log_event(
        db,
        event_type="caller_note_updated",
        area=PASS_GIVEAWAY_AREA,
        actor_email=actor_email,
        actor_role="promotions",
        entity_type="on_air_caller",
        entity_id=caller.id,
        details={"before": before, "after": caller.note},
    )
    return caller


def unlink_phone(
    db: Session, caller_id: int, phone: str, actor_email: str
) -> Optional[OnAirCaller]:
    """
    Take one number out of a caller. A caller left with one number is deleted.

    Raises:
        LookupError: No such caller, or the number isn't in it

    Returns:
        The caller, or None when it was deleted
    """
    caller = get_caller(db, caller_id)
    digits = stored_phone(phone)
    row = next((p for p in caller.phones if p.phone == digits), None)
    if row is None:
        raise LookupError("That phone number isn't linked to this caller")
    caller.phones.remove(row)
    deleted = len(caller.phones) < 2
    remaining = [p.phone for p in caller.phones]
    if deleted:
        db.delete(caller)
    else:
        caller.updated_at = datetime.now(timezone.utc)
    db.commit()
    audit_service.log_event(
        db,
        event_type="caller_phone_unlinked",
        area=PASS_GIVEAWAY_AREA,
        actor_email=actor_email,
        actor_role="promotions",
        entity_type="on_air_caller",
        entity_id=caller_id,
        details={"phone": digits, "remaining_phones": remaining, "caller_deleted": deleted},
    )
    if deleted:
        return None
    db.refresh(caller)
    return caller


def unlink_caller(db: Session, caller_id: int, actor_email: str) -> None:
    """Unlink every number of a caller."""
    caller = get_caller(db, caller_id)
    phones = [p.phone for p in caller.phones]
    note = caller.note
    db.delete(caller)
    db.commit()
    audit_service.log_event(
        db,
        event_type="caller_unlinked",
        area=PASS_GIVEAWAY_AREA,
        actor_email=actor_email,
        actor_role="promotions",
        entity_type="on_air_caller",
        entity_id=caller_id,
        details={"phones": phones, "note": note},
    )


def dismiss(db: Session, phones: Iterable[str], actor_email: str) -> list[list[str]]:
    """
    Not the same person: dismiss every pair of the numbers that aren't
    already one caller (decision 9).

    Raises:
        ValueError: Fewer than two numbers, or nothing left to dismiss

    Returns:
        The pairs dismissed
    """
    numbers = _clean_phones(phones)
    if len(numbers) < 2:
        raise ValueError("Pick at least two phone numbers")
    state = LinkState.load(db)
    added = []
    for a, b in combinations(numbers, 2):
        if state.person_key(a) == state.person_key(b):
            continue
        if _pair(phone_key(a), phone_key(b)) in state.dismissed:
            continue
        db.add(DismissedCallerPair(phone_a=a, phone_b=b, dismissed_by=actor_email))
        added.append([a, b])
    if not added:
        raise ValueError("These phone numbers are already linked or dismissed")
    db.commit()
    audit_service.log_event(
        db,
        event_type="caller_suggestion_dismissed",
        area=PASS_GIVEAWAY_AREA,
        actor_email=actor_email,
        actor_role="promotions",
        entity_type="on_air_caller_suggestion",
        details={"phones": numbers, "pairs": added},
    )
    return added


def undismiss(db: Session, phones: Iterable[str], actor_email: str) -> list[list[str]]:
    """Undo dismissing the pairs among *phones*. Returns the pairs removed."""
    numbers = _clean_phones(phones)
    removed = []
    for pair in db.query(DismissedCallerPair).filter(
        DismissedCallerPair.phone_a.in_(numbers), DismissedCallerPair.phone_b.in_(numbers)
    ):
        removed.append([pair.phone_a, pair.phone_b])
        db.delete(pair)
    if not removed:
        raise ValueError("None of these phone numbers were dismissed")
    db.commit()
    audit_service.log_event(
        db,
        event_type="caller_dismissal_undone",
        area=PASS_GIVEAWAY_AREA,
        actor_email=actor_email,
        actor_role="promotions",
        entity_type="on_air_caller_suggestion",
        details={"phones": numbers, "pairs": removed},
    )
    return removed


def common_names(db: Session) -> list[CommonCallerName]:
    """Names marked too common to suggest, alphabetically."""
    return db.query(CommonCallerName).order_by(CommonCallerName.name).all()


def mark_common(db: Session, name: str, actor_email: str) -> CommonCallerName:
    """
    Mark a name too common to suggest linking its numbers.

    Raises:
        ValueError: A blank name
    """
    normalized = normalize_person_name(name)
    if not normalized:
        raise ValueError("Enter a name")
    row = db.query(CommonCallerName).filter(CommonCallerName.name == normalized).first()
    if row is not None:
        return row
    row = CommonCallerName(name=normalized, marked_by=actor_email)
    db.add(row)
    db.commit()
    db.refresh(row)
    audit_service.log_event(
        db,
        event_type="caller_name_marked_common",
        area=PASS_GIVEAWAY_AREA,
        actor_email=actor_email,
        actor_role="promotions",
        entity_type="on_air_caller_suggestion",
        details={"name": normalized},
    )
    return row


def unmark_common(db: Session, name: str, actor_email: str) -> None:
    """
    Raises:
        LookupError: The name isn't marked
    """
    normalized = normalize_person_name(name)
    row = db.query(CommonCallerName).filter(CommonCallerName.name == normalized).first()
    if row is None:
        raise LookupError("That name isn't marked as too common")
    db.delete(row)
    db.commit()
    audit_service.log_event(
        db,
        event_type="caller_name_unmarked_common",
        area=PASS_GIVEAWAY_AREA,
        actor_email=actor_email,
        actor_role="promotions",
        entity_type="on_air_caller_suggestion",
        details={"name": normalized},
    )
