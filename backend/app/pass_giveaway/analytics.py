"""
The Radio Pass Giveaway's metrics for KALX Staff Analytics.

`main.py` registers `METRIC_GROUPS` in `analytics_registry`. Every metric
says how it's calculated in its explanation, which the analytics page shows
in the metric's ⓘ popover, so keep the two in step when changing either.

Shared rules (spec: docs/analytics/specs/analytics-site/plan.md):

- Shows count when they're published or closed and their show date is in
  the window. Utilization only counts the ones that are also complete:
  closed, or with a show date before today.
- Everything about a show (giveaways, attempts, page visits, popups, wins,
  win-limit warnings, staff pass claims) is placed by that show's date, not
  by when it happened, so every tab's numbers agree (decision Q1 of
  docs/analytics/specs/analytics-improvements/plan.md). Only guest sessions
  count by when they happened.
- A venue or DJ with fewer than `LOW_SAMPLE` shows or visits is flagged and
  left out of rankings.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Callable, Iterable, Optional

from sqlalchemy.orm import Session, selectinload

from app.auth import _staff_statuses
from app.common.services import tracking_service
from app.common.services.analytics_metrics import (
    LOW_SAMPLE,
    TOP_ROWS,
    column,
    explanation,
    heatmap,
    median,
    ratio,
    series,
    stat,
    table,
)
from app.common.services.analytics_registry import MetricGroup, Params
from app.common.services.analytics_window import Window, today_pacific
from app.common.services.tracking_service import (
    DJ_STUDIO_NETWORK,
    STATION_OFFICE_NETWORK,
    as_utc,
    normalize_person_name,
    normalize_phone,
    pacific_date,
)
from app.models.audit_log import AuditLog
from app.models.lottery_entry import LotteryEntry
from app.models.on_air_winner import OnAirWinner
from app.models.pass_model import Pass
from app.models.promoter import Promoter
from app.models.show import Show
from app.models.show_attempt import ShowAttempt
from app.models.specialty_show import SpecialtyShow
from app.models.spinitron_persona import SpinitronPersona
from app.models.credit import UNATTRIBUTED
from app.models.staff import Staff
from app.models.venue import Venue, venue_sort_key
from app.pass_giveaway.services.caller_names import (
    group_similar_names,
    is_same_caller_name,
)
from app.pass_giveaway.services.linked_callers import (
    RESOLVED,
    STATUS_LABELS,
    LinkState,
    bypasses_win_limit,
    venue_win_limits,
)
from app.pass_giveaway.services.tracking import (
    GIVEAWAY_VISIT,
    GUEST_SESSION,
    SPIN_MATCH_GIVEAWAY,
    SPIN_MATCH_SUGGESTED,
)

COUNTED_STATUSES = ("published", "closed")

# The DJ page's URL key for visits with no DJ name
UNKNOWN_DJ_KEY = "unknown"

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# Show start times: (label, start inclusive, end exclusive)
SHOW_TIME_BUCKETS = [
    ("Before 6pm", time(0, 0), time(18, 0)),
    ("6–9pm", time(18, 0), time(21, 0)),
    ("After 9pm", time(21, 0), None),
]

LEAD_TIME_BUCKETS = [
    ("Under 7 days", 0, 7),
    ("7–14 days", 7, 15),
    ("15–30 days", 15, 31),
    ("Over 30 days", 31, None),
]

OUTCOME_LABELS = {"given_away": "Given away", "tried": "Tried", "neither": "Neither"}

# ---------------------------------------------------------------------------
# Explanation text shared by several metrics

_SHOW_SCOPE = "Published and closed shows. Draft and deleted shows are left out."
_COMPLETE = (
    "Only complete shows count: closed, or with a show date before today. Future"
    " shows still have passes on offer, so counting them would understate usage."
)
_ON_AIR_FORMULA = "Pass pairs given away ÷ pass pairs."
_STAFF_FORMULA = (
    "Staff passes claimed ÷ staff passes. A +1 guest's seat is a staff pass, so a"
    " claimed guest seat counts as used."
)
_BALANCE_FORMULA = (
    "On-air utilization % − staff utilization %, in percentage points. Above 0,"
    " on-air passes are used more; below 0, staff passes are."
)
_LOW_SAMPLE_NOTE = (
    f"Venues with fewer than {LOW_SAMPLE} complete shows in the window are marked"
    ' "low sample" and aren\'t ranked.'
)
_VISIT_FORMULA = (
    "Each load of a show's \"I'm off the mic\" page in a tab is one visit (a reload"
    " within 10 minutes continues it). Its outcome is the best thing that happened"
    ' in it: a pass pair given away, else "tried" clicked, else neither.'
)
_VISIT_DJ = (
    "A visit belongs to who the Spinitron schedule had on air for its giveaway or"
    ' "tried" click, otherwise when the page was opened (or switched early to the'
    ' next DJ). With no one on air it counts as "Unattributed".'
)
_VISIT_EXCLUDES = "Promotions staff previewing the DJ view, and impersonation."
_DJ_NAMES = (
    "Each DJ persona and each Specialty Music Show or Talk & Info Show is its own row,"
    " named as it is now. A giveaway during a music show counts for the show; one made"
    ' while no one was on air is "Unattributed".'
)
_WINNERS = (
    "Winners are matched by phone number, digits only and without a leading 1. Phone"
    " numbers linked as one caller in Promotions → Admin (Linked Callers) count as one"
    " winner. The name and phone shown are the most recent ones used."
)
_SHOW_DATE = "Show date"
_ANNOUNCED_FORMULA = (
    'Complete shows with at least one pass pair given away or one "tried" click ÷'
    " complete shows: how many shows get announced on air."
)
_GIVEN_HELP = "Pass pairs given away on air."
_TRIED_HELP = 'Times a DJ clicked "tried": a giveaway announced on air that got no callers.'
_LEAD_HELP = "The median number of days from publishing a show to its show date."
_FIRST_GIVEAWAY_HELP = (
    "The median number of days from publishing a show to its first pass pair given"
    " away, for shows with a giveaway."
)
_UNUSED_PAIRS_HELP = "Pass pairs still available on complete shows."
_WARNINGS_HELP = (
    "Times a DJ was warned a caller won at this venue (or one sharing its win limit)"
    " too recently, once per phone number, show and day."
)
_TOTAL_HELP = (
    'Pass pairs given away + "tried" clicks: how many times a giveaway was announced'
    " on air."
)

# Where a similar name links to: its group in Promotions → Admin's Linked
# Callers section (linked callers decision 17)
LINKED_CALLERS_LINK = "/pass-giveaway/promotions/admin?caller={name}#linked-callers"

# A winner's page in the analytics site, by one of their wins' IDs
WINNER_LINK = "/winners/{win_id}"

# Win-limit block outcomes
BLOCKED = "Blocked"
OVERRIDDEN = "Overridden"
WON_ANOTHER_NUMBER = "Won with another number"


# ---------------------------------------------------------------------------
# Loading


def _in_window(window: Window, venue_id: Optional[int] = None) -> list:
    """Filters for counted shows with a show date in *window* (and at the venue)."""
    filters = [
        Show.status.in_(COUNTED_STATUSES),
        Show.show_date >= window.start,
        Show.show_date <= window.end,
    ]
    if venue_id is not None:
        filters.append(Show.venue_id == venue_id)
    return filters


def _shows_in_scope(
    db: Session,
    window: Window,
    venue_id: Optional[int] = None,
) -> list[Show]:
    return (
        db.query(Show)
        .options(
            selectinload(Show.passes),
            selectinload(Show.venue).selectinload(Venue.owners),
            selectinload(Show.promoter).selectinload(Promoter.owners),
        )
        .filter(*_in_window(window, venue_id))
        .all()
    )


def _show_ids_in_window(
    db: Session, window: Window, venue_id: Optional[int] = None
) -> set[int]:
    return {i for (i,) in db.query(Show.id).filter(*_in_window(window, venue_id))}


def _completed(shows: Iterable[Show], today: date) -> list[Show]:
    return [s for s in shows if s.status == "closed" or s.show_date < today]


@dataclass
class _Usage:
    shows: int = 0
    pairs: int = 0
    given: int = 0
    staff: int = 0
    claimed: int = 0

    def add(self, show: Show) -> None:
        self.shows += 1
        for p in show.passes:
            if p.pass_type == "pair":
                self.pairs += 1
                if p.status == "given_away":
                    self.given += 1
            elif p.pass_type == "staff":
                self.staff += 1
                if p.status == "claimed":
                    self.claimed += 1

    @property
    def on_air(self) -> Optional[float]:
        return ratio(self.given, self.pairs)

    @property
    def staff_rate(self) -> Optional[float]:
        return ratio(self.claimed, self.staff)

    @property
    def combined(self) -> Optional[float]:
        return ratio(self.given + self.claimed, self.pairs + self.staff)

    @property
    def balance(self) -> Optional[float]:
        if self.on_air is None or self.staff_rate is None:
            return None
        return (self.on_air - self.staff_rate) * 100


def _usage(shows: Iterable[Show]) -> _Usage:
    u = _Usage()
    for s in shows:
        u.add(s)
    return u


def _who(persona_id: Optional[int], specialty_show_id: Optional[int]) -> Optional[str]:
    """
    The DJs tab row a record belongs to: its show (a Specialty Music Show or
    Talk & Info Show slot, so each show gets its own row), else its persona,
    else None (unattributed). See decision 29 of
    docs/pass-giveaway/specs/spinitron-identity/plan.md.
    """
    if specialty_show_id is not None:
        return f"show-{specialty_show_id}"
    if persona_id is not None:
        return f"persona-{persona_id}"
    return None


def _dj_display_names(db: Session) -> dict[str, str]:
    """Row key → the persona's or show's current name, for every persona and show."""
    names = {
        f"persona-{pid}": name
        for pid, name in db.query(SpinitronPersona.id, SpinitronPersona.name)
    }
    names.update({
        f"show-{sid}": name for sid, name in db.query(SpecialtyShow.id, SpecialtyShow.name)
    })
    return names


def _dj_label(key: Optional[str], names: dict[str, str]) -> str:
    if not key:
        return UNATTRIBUTED
    if key in names:
        return names[key]
    kind, _, number = key.partition("-")
    return f"Persona #{number}" if kind == "persona" else f"Show #{number}"


def _dj_link_key(key: Optional[str]) -> str:
    return key or UNKNOWN_DJ_KEY


def _given_by(p: Pass) -> Optional[str]:
    return _who(p.given_away_persona_id, p.given_away_specialty_show_id)


def _tried_by(a: ShowAttempt) -> Optional[str]:
    return _who(a.persona_id, a.specialty_show_id)


def _giveaways_in_window(db: Session, window: Window, venue_id: Optional[int] = None):
    """Pass pairs given away for shows with a show date in the window."""
    return (
        db.query(Pass)
        .join(Show, Show.id == Pass.show_id)
        .options(selectinload(Pass.show).selectinload(Show.venue))
        .filter(
            Pass.pass_type == "pair",
            Pass.status == "given_away",
            *_in_window(window, venue_id),
        )
        .all()
    )


def _attempts_in_window(db: Session, window: Window, venue_id: Optional[int] = None):
    """The "tried" clicks for shows with a show date in the window."""
    return (
        db.query(ShowAttempt)
        .join(Show, Show.id == ShowAttempt.show_id)
        .options(selectinload(ShowAttempt.show).selectinload(Show.venue))
        .filter(*_in_window(window, venue_id))
        .all()
    )


@dataclass
class _Visit:
    show_id: Optional[int]
    dj: Optional[str]
    outcome: str
    count: int


def _visits(db: Session, window: Window, venue_id: Optional[int] = None) -> list[_Visit]:
    """Giveaway page visits for shows with a show date in the window."""
    return [
        _Visit(
            c.entity_id,
            _who(c.persona_id, c.specialty_show_id),
            c.dimension or "neither",
            c.count,
        )
        for c in tracking_service.entity_event_counts(
            db, [GIVEAWAY_VISIT], "show", _show_ids_in_window(db, window, venue_id)
        )
    ]


def _funnel(visits: Iterable[_Visit]) -> dict[str, int]:
    counts = Counter()
    for v in visits:
        counts[v.outcome] += v.count
    return counts


def _funnel_row(counts: dict[str, int]) -> dict:
    total = sum(counts.values())
    return {
        "visits": total,
        "given_away": ratio(counts.get("given_away", 0), total),
        "tried": ratio(counts.get("tried", 0), total),
        "neither": ratio(counts.get("neither", 0), total),
    }


def _creators(db: Session, show_ids: Iterable[int]) -> dict[int, str]:
    """Show ID → the email of whoever filled out its new show form."""
    ids = list(show_ids)
    if not ids:
        return {}
    rows = (
        db.query(AuditLog.entity_id, AuditLog.actor_email)
        .filter(
            AuditLog.event_type == "show_created",
            AuditLog.entity_type == "show",
            AuditLog.entity_id.in_(ids),
        )
        .all()
    )
    return {show_id: email for show_id, email in rows if email}


def _owner_emails(owner_rows) -> set[str]:
    return {o.staff.email for o in owner_rows if o.staff is not None}


def _staff_names(db: Session, emails: Iterable[str]) -> dict[str, str]:
    emails = {e for e in emails if e}
    if not emails:
        return {}
    return dict(db.query(Staff.email, Staff.name).filter(Staff.email.in_(emails)).all())


def _params_venue_id(params: Params) -> Optional[int]:
    try:
        return int(params.get("venue_id", ""))
    except ValueError:
        return None


def _dj_from_params(params: Params) -> Optional[str]:
    """The DJ page's row key (see `_who`), or None for unattributed."""
    key = params.get("dj", "")
    return None if key == UNKNOWN_DJ_KEY else key


# ---------------------------------------------------------------------------
# Utilization tables


_COMPLETE_SHOWS_HELP = "Shows that are closed or whose show date is before today."
_ON_AIR_HELP = f"{_ON_AIR_FORMULA} On complete shows."
_STAFF_HELP = f"{_STAFF_FORMULA} On complete shows."

_UTILIZATION_COLUMNS = [
    column("shows", "Complete shows", "number", help=_COMPLETE_SHOWS_HELP),
    column("on_air", "On-air utilization", "percent", help=_ON_AIR_HELP),
    column("staff", "Staff utilization", "percent", help=_STAFF_HELP),
    column("balance", "Balance", "points", help=_BALANCE_FORMULA),
]


def _utilization_row(u: _Usage) -> dict:
    return {
        "shows": u.shows,
        "on_air": u.on_air,
        "staff": u.staff_rate,
        "balance": u.balance,
        "combined": u.combined,
        "_low_sample": u.shows < LOW_SAMPLE,
    }


def _utilization_by(
    shows: Iterable[Show], key: Callable[[Show], object]
) -> dict[object, _Usage]:
    groups: dict[object, _Usage] = defaultdict(_Usage)
    for s in shows:
        groups[key(s)].add(s)
    return groups


def _top_venue_tables(completed: list[Show]) -> list[dict]:
    by_venue = _utilization_by(completed, lambda s: s.venue)
    ranked = [(v, u) for v, u in by_venue.items() if u.shows >= LOW_SAMPLE]
    expl_base = f"{_SHOW_SCOPE} {_COMPLETE} {_LOW_SAMPLE_NOTE}"
    cols = [
        column("venue", "Venue", "text", link="/venues/{venue_id}"),
        column("shows", "Complete shows", "number", help=_COMPLETE_SHOWS_HELP),
    ]
    out = []
    for metric_id, title, attr, formula, label in [
        (
            "top_venues_on_air",
            "Top venues by on-air utilization",
            "on_air",
            _ON_AIR_FORMULA,
            "On-air",
        ),
        (
            "top_venues_staff",
            "Top venues by staff utilization",
            "staff_rate",
            _STAFF_FORMULA,
            "Staff",
        ),
        (
            "top_venues_combined",
            "Top venues by combined utilization",
            "combined",
            "(Pass pairs given away + staff passes claimed) ÷ (pass pairs + staff passes).",
            "Combined",
        ),
    ]:
        rows = sorted(
            (
                {
                    "venue": v.name,
                    "venue_id": v.id,
                    "shows": u.shows,
                    "value": getattr(u, attr),
                }
                for v, u in ranked
                if getattr(u, attr) is not None
            ),
            key=lambda r: r["value"],
            reverse=True,
        )
        out.append(
            table(
                metric_id,
                title,
                cols + [column("value", label, "percent", help=formula)],
                rows,
                explanation(formula, "Show date", includes=expl_base),
                top=TOP_ROWS,
            )
        )
    return out


# ---------------------------------------------------------------------------
# Winners


@dataclass
class _Win:
    id: int
    name: str
    phone: str
    email: Optional[str]
    venue_id: int
    venue: str
    show_id: int
    show: str
    show_date: Optional[date]
    dj: str
    won_at: datetime


def _wins(db: Session, venue_id: Optional[int] = None) -> list[_Win]:
    """Every on-air win at any time (at the venue), oldest first."""
    q = db.query(OnAirWinner).options(
        selectinload(OnAirWinner.show), selectinload(OnAirWinner.venue)
    )
    if venue_id is not None:
        q = q.filter(OnAirWinner.venue_id == venue_id)
    wins = [
        _Win(
            id=w.id,
            name=w.recipient_name,
            phone=normalize_phone(w.recipient_phone),
            email=(w.recipient_email or "").strip().lower() or None,
            venue_id=w.venue_id,
            venue=w.venue.name if w.venue else "",
            show_id=w.show_id,
            show=w.show.event_name if w.show else "",
            show_date=w.show.show_date if w.show else None,
            dj=w.given_away_by,
            won_at=as_utc(w.created_at),
        )
        for w in q.all()
    ]
    wins.sort(key=lambda w: (w.won_at, w.id))
    return wins


def _in(window: Window, w) -> bool:
    """Whether a win or block's show date is in the window."""
    return w.show_date is not None and window.contains_date(w.show_date)


def _by_person(wins: Iterable[_Win], state: LinkState) -> dict[str, list[_Win]]:
    """Person key (see `LinkState.person_key`) → their wins, oldest first."""
    out: dict[str, list[_Win]] = defaultdict(list)
    for w in wins:
        if w.phone:
            out[state.person_key(w.phone)].append(w)
    return out


_WIN_DATE = "Show date of the show won"
_WIN_ROW_COLUMNS = [
    column("won", "Won", "date", help="The day the pass pair was given away."),
    column("winner", "Name", help="The name the DJ typed in for this win."),
    column("phone", "Phone", "phone", help="The phone number the DJ typed in."),
    column("email", "Email", help="The winner's email, when the venue asks for one."),
    column("show", "Show"),
    column("show_date", "Show date", "date", help="The date of the show won."),
    column("venue", "Venue"),
    column("dj", "DJ", help="Who gave the pass pair away, as credited."),
]


def _win_row(w: _Win) -> dict:
    return {
        "won": pacific_date(w.won_at).isoformat(),
        "winner": w.name,
        "phone": w.phone,
        "email": w.email,
        "show": w.show,
        "show_date": w.show_date.isoformat() if w.show_date else None,
        "venue": w.venue,
        "dj": w.dj,
    }


def _repeat_winners_table(
    wins: list[_Win], window: Window, state: LinkState, metric_id: str
) -> dict:
    rows = []
    for ws in _by_person((w for w in wins if _in(window, w)), state).values():
        if len(ws) < 2:
            continue
        rows.append({
            "name": ws[-1].name,
            "win_id": ws[-1].id,
            "phone": ws[-1].phone,
            "phones": len({w.phone for w in ws}),
            "wins": len(ws),
            "venues": ", ".join(sorted({w.venue for w in ws})),
            "dates": ", ".join(pacific_date(w.won_at).isoformat() for w in ws),
        })
    rows.sort(key=lambda r: (-r["wins"], r["name"].lower()))
    return table(
        metric_id,
        "Top repeat on-air winners",
        [
            column("name", "Name", link=WINNER_LINK),
            column("phone", "Phone", "phone", help="The phone number of their latest win."),
            column(
                "phones",
                "Phone numbers",
                "number",
                help="How many of a linked caller's numbers won in the window.",
            ),
            column("wins", "Wins", "number", help="On-air wins in the window."),
            column("venues", "Venues", help="The venues of those wins."),
            column("dates", "Dates won", help="The days those pass pairs were given away."),
        ],
        rows,
        explanation(
            "Winners with two or more on-air wins for shows in the window, most wins"
            " first. Click a name for the winner's page.",
            _WIN_DATE,
            includes=_WINNERS,
        ),
        top=TOP_ROWS,
    )


def _same_name_table(
    wins: list[_Win],
    window: Window,
    win_limits: dict[int, tuple[int, Optional[int]]],
    state: LinkState,
    metric_id: str,
) -> dict:
    normalized = {id(w): normalize_person_name(w.name) for w in wins}
    groups = group_similar_names(normalized.values())
    by_name: dict[str, list[_Win]] = defaultdict(list)
    for w in wins:
        key = normalized[id(w)]
        if key:
            by_name[groups[key]].append(w)
    rows = []
    for ws in by_name.values():
        phones = {w.phone for w in ws if w.phone}
        if len(phones) < 2 or not any(_in(window, w) for w in ws):
            continue
        ws.sort(key=lambda w: w.won_at)
        flagged = bypasses_win_limit(ws, win_limits)
        status = state.status(phones, {normalized[id(w)] for w in ws})
        emails_by_phone: dict[str, set[str]] = defaultdict(set)
        for w in ws:
            if w.email:
                emails_by_phone[w.email].add(w.phone)
        same_email = any(len(p) > 1 for p in emails_by_phone.values())
        # The latest spelling of each normalized name, latest first
        spellings: dict[str, str] = {}
        for w in reversed(ws):
            spellings.setdefault(normalized[id(w)], w.name.strip())
        rows.append({
            "name": ws[-1].name,
            "spellings": ", ".join(spellings.values()) if len(spellings) > 1 else "",
            "phones": len(phones),
            "wins": len(ws),
            "same_venue_in_limit": "Yes" if flagged else "No",
            "same_email": "Yes" if same_email else "No",
            "status": STATUS_LABELS[status],
            # Only while it still needs reviewing (linked callers decision 13)
            "_flag": flagged and status not in RESOLVED,
            "_details": {"columns": _WIN_ROW_COLUMNS, "rows": [_win_row(w) for w in ws]},
        })
    rows.sort(key=lambda r: (not r["_flag"], -r["phones"], r["name"].lower()))
    return table(
        metric_id,
        "Similar names, different phone numbers",
        [
            column("name", "Name", link=LINKED_CALLERS_LINK, external=True),
            column(
                "spellings",
                "Spellings",
                help="Every spelling grouped under this name, latest first.",
            ),
            column(
                "phones",
                "Phone numbers",
                "number",
                help="Different phone numbers this name won with, at any time.",
            ),
            column("wins", "Wins", "number", help="This name's on-air wins at any time."),
            column(
                "same_venue_in_limit",
                "Same venue or sister venue within limit",
                help=(
                    "Yes when two of its numbers won at the same venue, or at venues"
                    " sharing a win limit, closer together (days between show dates)"
                    " than the limit allows: how someone could get around it."
                ),
            ),
            column(
                "same_email",
                "Same email on different numbers",
                help="Yes when one email address was given with two of its numbers.",
            ),
            column(
                "status",
                "Status",
                help=(
                    "Linked (all its numbers are one caller), Partly linked, Dismissed"
                    " (marked different people), Common name, or Unreviewed."
                ),
            ),
        ],
        rows,
        explanation(
            "On-air winners whose name, or names spelled almost the same way, have two or"
            " more different phone numbers. A name is listed when it has a win for a show"
            " in the window, and is compared with its wins at any time. It's highlighted"
            " while it could be someone getting around a win limit and hasn't been"
            " linked, dismissed or marked a common name in Promotions → Admin (Linked"
            " Callers; the name links there). The same email on different numbers is"
            " stronger evidence that it's one person.",
            f"{_WIN_DATE} (for the window); all wins for comparison",
            includes=(
                "DJs often misspell a caller's name, so names match ignoring case,"
                " spacing and punctuation when their first and last names each match"
                " with one typo, or sound alike and are spelled nearly the same, and"
                " their middle names (if both have any) match, with an initial"
                ' matching a middle name ("Jon Smith", "John Smtih", "John A. Smith"'
                ' and "John Allen Smith" are one name, as are "Steven" and "Stephen").'
                " One typo can't tell"
                ' "Jane" from "Jake", and two different people can share a name,'
                " so check the wins before acting on a row. Venues with no win limit"
                " never highlight a name."
            ),
        ),
        top=TOP_ROWS,
    )


def _repeat_share(wins: list[_Win], window: Window, state: LinkState) -> dict:
    all_time = Counter(state.person_key(w.phone) for w in wins if w.phone)
    in_window = [w for w in wins if _in(window, w) and w.phone]
    repeat = sum(1 for w in in_window if all_time[state.person_key(w.phone)] > 1)
    return stat(
        "repeat_winner_share",
        "Wins going to repeat winners",
        ratio(repeat, len(in_window)),
        "percent",
        explanation(
            "On-air wins for shows in the window that went to a winner with more than"
            " one win at any time ÷ on-air wins for shows in the window.",
            _WIN_DATE,
            includes=_WINNERS,
        ),
        note=f"{repeat} of {len(in_window)} wins",
    )


# ---------------------------------------------------------------------------
# Win-limit blocks


@dataclass
class _Block:
    at: datetime
    phone: str
    person: str
    show_id: int
    show: str
    show_date: Optional[date]
    venue_id: Optional[int]
    venue: str
    outcome: str = BLOCKED


def _blocks(
    db: Session, wins: list[_Win], state: LinkState, venue_id: Optional[int] = None
) -> list[_Block]:
    """
    Every win-limit block at any time (at the venue), oldest first: the
    warnings DJs saw that a caller won too recently, once per (phone, show,
    day), each with its outcome (decision Q14).
    """
    first: dict[tuple[str, int, date], AuditLog] = {}
    for r in (
        db.query(AuditLog)
        .filter(AuditLog.event_type == "winner_frequency_warning")
        .order_by(AuditLog.occurred_at)
    ):
        details = r.details or {}
        phone = normalize_phone(details.get("recipient_phone"))
        show_id = details.get("show_id")
        if not phone or show_id is None:
            continue
        first.setdefault((phone, show_id, pacific_date(r.occurred_at)), r)
    if not first:
        return []
    shows = {
        s.id: s
        for s in (
            db.query(Show)
            .options(selectinload(Show.venue))
            .filter(Show.id.in_({k[1] for k in first}))
        )
    }

    # (person, show) pairs a DJ gave a pass to despite the warning
    override_pass_ids = [
        r.entity_id
        for r in db.query(AuditLog).filter(
            AuditLog.event_type == "venue_frequency_override",
            AuditLog.entity_type == "pass",
        )
        if r.entity_id
    ]
    overridden = {
        (state.person_key(normalize_phone(phone)), show_id)
        for phone, show_id in db.query(
            OnAirWinner.recipient_phone, OnAirWinner.show_id
        ).filter(OnAirWinner.pass_id.in_(override_pass_ids or [-1]))
    }
    names: dict[str, set[str]] = defaultdict(set)
    wins_by_show: dict[int, list[_Win]] = defaultdict(list)
    for w in wins:
        if w.phone:
            names[state.person_key(w.phone)].add(normalize_person_name(w.name))
        wins_by_show[w.show_id].append(w)

    out = []
    for (phone, show_id, _day), r in first.items():
        show = shows.get(show_id)
        if show is None or (venue_id is not None and show.venue_id != venue_id):
            continue
        person = state.person_key(phone)
        at = as_utc(r.occurred_at)
        if (person, show_id) in overridden:
            outcome = OVERRIDDEN
        elif any(
            w.won_at >= at
            and state.person_key(w.phone) != person
            and any(
                is_same_caller_name(normalize_person_name(w.name), n) for n in names[person]
            )
            for w in wins_by_show[show_id]
        ):
            outcome = WON_ANOTHER_NUMBER
        else:
            outcome = BLOCKED
        out.append(
            _Block(
                at=at,
                phone=phone,
                person=person,
                show_id=show_id,
                show=show.event_name,
                show_date=show.show_date,
                venue_id=show.venue_id,
                venue=show.venue.name if show.venue else "",
                outcome=outcome,
            )
        )
    out.sort(key=lambda b: b.at)
    return out


_BLOCK_OUTCOME_HELP = (
    f"{OVERRIDDEN}: the DJ gave this caller the pass anyway. {WON_ANOTHER_NUMBER}:"
    " someone with a similar name won this show on a different phone number after"
    f" the warning, which could be the caller getting around the limit. {BLOCKED}:"
    " neither."
)
_BLOCK_COLUMNS = [
    column("day", "Warned", "date", help="The day the DJ saw the warning."),
    column("phone", "Phone", "phone", help="The phone number the DJ typed in."),
    column("show", "Show"),
    column("show_date", "Show date", "date", help="The date of the show they called for."),
    column("venue", "Venue"),
    column("outcome", "Outcome", help=_BLOCK_OUTCOME_HELP),
]


def _block_row(b: _Block) -> dict:
    return {
        "day": pacific_date(b.at).isoformat(),
        "phone": b.phone,
        "show": b.show,
        "show_date": b.show_date.isoformat() if b.show_date else None,
        "venue": b.venue,
        "outcome": b.outcome,
        "_flag": b.outcome != OVERRIDDEN,
    }


_BLOCK_INCLUDES = (
    "A DJ sees the warning when they type in a caller's phone number on the"
    " giveaway form and it (or a number linked to it) won at the venue, or a venue"
    " sharing its win limit, too recently. It's counted once per phone number, show"
    " and day, however many times the form checked it."
)


def _latest_wins(wins: list[_Win], state: LinkState) -> dict[str, _Win]:
    """Person key → their latest win."""
    return {person: ws[-1] for person, ws in _by_person(wins, state).items()}


def _blocks_table(
    blocks: list[_Block], latest: dict[str, _Win], metric_id: str, title: str
) -> dict:
    rows = []
    for b in blocks:
        win = latest.get(b.person)
        row = _block_row(b)
        rows.append({
            "name": win.name if win else "Unknown",
            "win_id": win.id if win else None,
            **row,
        })
    rows.reverse()
    return table(
        metric_id,
        title,
        [column("name", "Name", link=WINNER_LINK)] + _BLOCK_COLUMNS,
        rows,
        explanation(
            "Callers a DJ was warned had won too recently, latest first. Blocked and"
            " won-with-another-number rows are highlighted. Click a name for the"
            " winner's page.",
            "Show date of the show they called for",
            includes=_BLOCK_INCLUDES,
            excludes=(
                "The name is the one on the caller's latest win; it isn't recorded with"
                " the warning."
            ),
        ),
        top=TOP_ROWS,
    )


# ---------------------------------------------------------------------------
# On-air winners tab and winner page


def build_winners(db: Session, window: Window, params: Params) -> list[dict]:
    wins = _wins(db)
    links = LinkState.load(db)
    blocks = [b for b in _blocks(db, wins, links) if _in(window, b)]
    latest = _latest_wins(wins, links)
    all_time = _by_person(wins, links)
    in_window = _by_person((w for w in wins if _in(window, w)), links)
    blocks_by_person = Counter(b.person for b in blocks)

    rows = []
    for person, ws in in_window.items():
        last = latest[person]
        rows.append({
            "name": last.name,
            "win_id": last.id,
            "phone": last.phone,
            "wins": len(ws),
            "all_time": len(all_time[person]),
            "venues": ", ".join(sorted({w.venue for w in ws})),
            "last_won": pacific_date(last.won_at).isoformat(),
            "blocks": blocks_by_person[person],
        })
    rows.sort(key=lambda r: (-r["wins"], r["name"].lower()))
    outcomes = Counter(b.outcome for b in blocks)
    return [
        stat(
            "winners_count",
            "On-air winners",
            len(in_window),
            "number",
            explanation(
                "Different winners with an on-air win for a show in the window.",
                _WIN_DATE,
                includes=_WINNERS,
            ),
            note=f"{sum(len(ws) for ws in in_window.values())} wins",
        ),
        _repeat_share(wins, window, links),
        stat(
            "win_limit_blocks",
            "Win-limit blocks",
            len(blocks),
            "number",
            explanation(
                "Times a DJ was warned that a caller won too recently, for shows in the"
                " window.",
                "Show date of the show they called for",
                includes=_BLOCK_INCLUDES,
            ),
            note=(
                f"{outcomes[BLOCKED]} blocked, {outcomes[OVERRIDDEN]} overridden,"
                f" {outcomes[WON_ANOTHER_NUMBER]} won with another number"
            ),
        ),
        table(
            "winners",
            "On-air winners",
            [
                column("name", "Name", link=WINNER_LINK),
                column(
                    "phone", "Phone", "phone", help="The phone number of their latest win."
                ),
                column(
                    "wins", "Wins (window)", "number", help="Wins for shows in the window."
                ),
                column("all_time", "Wins (all time)", "number", help="Wins at any time."),
                column("venues", "Venues", help="The venues of their wins in the window."),
                column(
                    "last_won",
                    "Last won",
                    "date",
                    help="The day their latest pass pair was given away, at any time.",
                ),
                column(
                    "blocks",
                    "Blocks",
                    "number",
                    help="Win-limit warnings about them for shows in the window.",
                ),
            ],
            rows,
            explanation(
                "Everyone with an on-air win for a show in the window, most wins first."
                " Click a name for the winner's page.",
                _WIN_DATE,
                includes=f"{_WINNERS} The name shown is from their latest win.",
            ),
            top=TOP_ROWS,
        ),
        _blocks_table(blocks, latest, "blocked_by_win_limit", "Blocked by the win limit"),
        _repeat_winners_table(wins, window, links, "top_repeat_winners"),
        _same_name_table(
            wins, window, venue_win_limits(db), links, "same_name_different_phones"
        ),
    ]


def _params_win(db: Session, params: Params) -> Optional[OnAirWinner]:
    try:
        return db.get(OnAirWinner, int(params.get("win_id", "")))
    except ValueError:
        return None


def _winner_wins(
    db: Session, params: Params
) -> tuple[list[_Win], LinkState, Optional[str]]:
    """Every win, the link state, and the person key of the page's winner."""
    win = _params_win(db, params)
    if win is None:
        return [], LinkState(), None
    links = LinkState.load(db)
    return _wins(db), links, links.person_key(normalize_phone(win.recipient_phone))


def winner_title(db: Session, params: Params) -> Optional[str]:
    wins, links, person = _winner_wins(db, params)
    if person is None:
        return None
    mine = _by_person(wins, links).get(person)
    return mine[-1].name if mine else None


def build_winner(db: Session, window: Window, params: Params) -> list[dict]:
    wins, links, person = _winner_wins(db, params)
    if person is None:
        return []
    mine = _by_person(wins, links).get(person, [])
    blocks = [b for b in _blocks(db, wins, links) if b.person == person]
    in_window = [w for w in mine if _in(window, w)]

    by_phone: dict[str, list[_Win]] = defaultdict(list)
    for w in mine:
        by_phone[w.phone].append(w)
    phone_rows = sorted(
        (
            {
                "phone": phone,
                "name": ws[-1].name,
                "wins": len(ws),
                "last_won": pacific_date(ws[-1].won_at).isoformat(),
                "linked": "Yes" if links.caller_id(phone) is not None else "No",
            }
            for phone, ws in by_phone.items()
        ),
        key=lambda r: r["last_won"],
        reverse=True,
    )
    win_rows = [{**_win_row(w), "_flag": _in(window, w)} for w in reversed(mine)]
    return [
        stat(
            "winner_wins_window",
            "Wins in the window",
            len(in_window),
            "number",
            explanation(
                "This winner's on-air wins for shows in the window.",
                _WIN_DATE,
                includes=_WINNERS,
            ),
        ),
        stat(
            "winner_wins_all_time",
            "Wins at any time",
            len(mine),
            "number",
            explanation(
                "This winner's on-air wins, at any time.",
                "None: all time",
                includes=_WINNERS,
            ),
        ),
        stat(
            "winner_blocks",
            "Win-limit blocks",
            len(blocks),
            "number",
            explanation(
                "Times a DJ was warned this winner had won too recently, at any time.",
                "None: all time",
                includes=_BLOCK_INCLUDES,
            ),
            note=f"{sum(1 for b in blocks if _in(window, b))} for shows in the window",
        ),
        table(
            "winner_wins",
            "Wins",
            _WIN_ROW_COLUMNS,
            win_rows,
            explanation(
                "Every on-air win of this winner, latest first. Wins for shows in the"
                " window are highlighted; the others are shown because win limits look"
                " back further than the window.",
                "None: all time (highlight: show date)",
                includes=_WINNERS,
            ),
        ),
        table(
            "winner_blocks_table",
            "Win-limit blocks",
            _BLOCK_COLUMNS,
            [_block_row(b) for b in reversed(blocks)],
            explanation(
                "Every time a DJ was warned this winner had won too recently, latest"
                " first. Blocked and won-with-another-number rows are highlighted.",
                "None: all time",
                includes=_BLOCK_INCLUDES,
            ),
        ),
        table(
            "winner_phones",
            "Phone numbers",
            [
                column("phone", "Phone", "phone", help="A number this winner won with."),
                column(
                    "name",
                    "Latest name",
                    link=LINKED_CALLERS_LINK,
                    external=True,
                    help=(
                        "The name on this number's latest win. Click it to review the"
                        " caller in Promotions → Admin → Linked Callers."
                    ),
                ),
                column("wins", "Wins", "number", help="Wins on this number, at any time."),
                column(
                    "last_won",
                    "Last won",
                    "date",
                    help="The day this number's latest pass pair was given away.",
                ),
                column(
                    "linked",
                    "Linked",
                    help="Yes when this number is linked to a caller in Linked Callers.",
                ),
            ],
            phone_rows,
            explanation(
                "The phone numbers this winner won with: one, or every number of a linked"
                " caller. Link numbers that belong to one person, or review similar"
                " names, in Promotions → Admin → Linked Callers (click a name).",
                "None: all time",
                includes=_WINNERS,
            ),
        ),
    ]


# ---------------------------------------------------------------------------
# Who posts shows


def _owner_classes(show: Show, creator: str) -> str:
    if creator in _owner_emails(show.venue.owners if show.venue else []):
        return "venue_owner"
    if show.promoter and creator in _owner_emails(show.promoter.owners):
        return "promoter_owner"
    return "neither"


def _owners_of(show: Show) -> set[str]:
    """The emails of the show's owners: its promoter's reps, or the venue's."""
    promoted_by = show.promoted_by
    return _owner_emails(promoted_by.owners) if promoted_by is not None else set()


def _who_posts_table(db: Session, shows: list[Show], venue: Venue) -> dict:
    creators = _creators(db, [s.id for s in shows])
    counts: dict[str, Counter] = defaultdict(Counter)
    for s in shows:
        creator = creators.get(s.id)
        if creator:
            counts[creator][_owner_classes(s, creator)] += 1
        else:
            counts[""]["unknown"] += 1
    names = _staff_names(db, counts.keys())
    rows = []
    for email, c in counts.items():
        rows.append({
            "creator": names.get(email, email) if email else "Unknown creator",
            "shows": sum(c.values()),
            "venue_owner": c["venue_owner"],
            "promoter_owner": c["promoter_owner"],
            "neither": c["neither"],
            "_flag": c["neither"] > 0,
        })
    rows.sort(key=lambda r: -r["shows"])
    owner_names = sorted(o.staff.name for o in venue.owners if o.staff is not None)
    return table(
        "venue_creators",
        "Who posts this venue's shows",
        [
            column("creator", "Created by"),
            column("shows", "Shows", "number", help="This venue's shows they created."),
            column(
                "venue_owner",
                "As a venue owner",
                "number",
                help="Shows they created as one of the venue's promotions reps.",
            ),
            column(
                "promoter_owner",
                "As the show's promoter's owner",
                "number",
                help="Shows they created as one of the show's promoter's reps.",
            ),
            column(
                "neither",
                "As neither",
                "number",
                help="Shows they created without being one of their owners.",
            ),
        ],
        rows,
        explanation(
            "For each person who filled out the new show form for this venue's shows:"
            " how many of those shows they own as one of the venue's promotions reps, as"
            " one of the show's promoter's reps, or neither. Rows with \"neither\" shows"
            " are highlighted. The venue's reps today:"
            f" {', '.join(owner_names) or 'none'}.",
            "Show date",
            includes=f"{_SHOW_SCOPE} The creator comes from the audit log.",
            excludes=(
                "Shows created before the audit log existed (or imported) are under"
                ' "Unknown creator". Ownership is compared with today\'s reps.'
            ),
        ),
    )


# ---------------------------------------------------------------------------
# Venue-level extras


def _lead_days(show: Show) -> Optional[int]:
    if not show.published_at:
        return None
    days = (show.show_date - pacific_date(show.published_at)).days
    return days if days >= 0 else None


def _first_giveaway_days(show: Show) -> Optional[float]:
    if not show.published_at:
        return None
    times = [
        as_utc(p.given_away_at)
        for p in show.passes
        if p.pass_type == "pair" and p.status == "given_away" and p.given_away_at
    ]
    if not times:
        return None
    days = (min(times) - as_utc(show.published_at)).total_seconds() / 86400
    return days if days >= 0 else None


def _unused(shows: Iterable[Show]) -> tuple[int, int]:
    pairs = staff = 0
    for s in shows:
        for p in s.passes:
            if p.status == "available":
                if p.pass_type == "pair":
                    pairs += 1
                elif p.pass_type == "staff":
                    staff += 1
    return pairs, staff


def _lottery(
    db: Session, shows: list[Show]
) -> tuple[Optional[float], Optional[float], int]:
    """(entries ÷ staff passes, share of lottery shows oversubscribed, lottery shows)."""
    lottery_shows = [s for s in shows if s.lottery_enabled]
    if not lottery_shows:
        return None, None, 0
    ids = [s.id for s in lottery_shows]
    entries = Counter(
        show_id
        for (show_id,) in db.query(LotteryEntry.show_id).filter(
            LotteryEntry.show_id.in_(ids), LotteryEntry.entry_type == "staff"
        )
    )
    total_entries = sum(entries.values())
    staff_passes = sum(
        sum(1 for p in s.passes if p.pass_type == "staff") for s in lottery_shows
    )
    oversubscribed = sum(
        1
        for s in lottery_shows
        if entries[s.id] > sum(1 for p in s.passes if p.pass_type == "staff")
    )
    return (
        ratio(total_entries, staff_passes),
        ratio(oversubscribed, len(lottery_shows)),
        len(lottery_shows),
    )


def _alternates(db: Session, show_ids: set[int]) -> tuple[int, int]:
    """(joins, promotions to a pass) for alternate lists of these shows."""
    if not show_ids:
        return 0, 0
    joined = promoted = 0
    rows = db.query(AuditLog.event_type, AuditLog.details).filter(
        AuditLog.event_type.in_(["alternate_joined", "alternate_promoted"])
    )
    for event_type, details in rows:
        if (details or {}).get("show_id") not in show_ids:
            continue
        if event_type == "alternate_joined":
            joined += 1
        else:
            promoted += 1
    return joined, promoted


def _limit_counts(blocks: Iterable[_Block]) -> dict[Optional[int], Counter]:
    """Venue ID → counts of win-limit blocks ("warnings") and "overrides"."""
    out: dict[Optional[int], Counter] = defaultdict(Counter)
    for b in blocks:
        out[b.venue_id]["warnings"] += 1
        if b.outcome == OVERRIDDEN:
            out[b.venue_id]["overrides"] += 1
    return out


def _announced(completed: Iterable[Show], tried_show_ids: set[int]) -> tuple[int, int]:
    """(announced shows, complete shows): see `_ANNOUNCED_FORMULA`."""
    shows = list(completed)
    announced = sum(
        1
        for s in shows
        if s.id in tried_show_ids
        or any(p.pass_type == "pair" and p.status == "given_away" for p in s.passes)
    )
    return announced, len(shows)


def _preassigned(shows: Iterable[Show]) -> tuple[int, int]:
    pairs = pre = 0
    for s in shows:
        for p in s.passes:
            if p.pass_type == "pair":
                pairs += 1
                if p.is_preassigned:
                    pre += 1
    return pre, pairs


# ---------------------------------------------------------------------------
# Overview tab


def build_overview(db: Session, window: Window, params: Params) -> list[dict]:
    today = today_pacific()
    shows = _shows_in_scope(db, window)
    completed = _completed(shows, today)
    usage = _usage(completed)
    giveaways = _giveaways_in_window(db, window)
    attempts = _attempts_in_window(db, window)
    names = _dj_display_names(db)
    visits = _visits(db, window)
    visits_since = tracking_service.data_since(db, [GIVEAWAY_VISIT])
    announced, complete = _announced(completed, {a.show_id for a in attempts})

    metrics = [
        stat(
            "shows",
            "Shows",
            len(shows),
            "number",
            explanation(
                "Shows with a show date in the window.", _SHOW_DATE, includes=_SHOW_SCOPE
            ),
        ),
        stat(
            "on_air_utilization",
            "On-air utilization",
            usage.on_air,
            "percent",
            explanation(_ON_AIR_FORMULA, _SHOW_DATE, includes=f"{_SHOW_SCOPE} {_COMPLETE}"),
            note=f"{usage.given} of {usage.pairs} pass pairs",
        ),
        stat(
            "staff_utilization",
            "Staff utilization",
            usage.staff_rate,
            "percent",
            explanation(_STAFF_FORMULA, _SHOW_DATE, includes=f"{_SHOW_SCOPE} {_COMPLETE}"),
            note=f"{usage.claimed} of {usage.staff} staff passes",
        ),
        stat(
            "passes_given_away",
            "Pass pairs given away",
            len(giveaways),
            "number",
            explanation(
                "Pass pairs given away on air for shows in the window, including"
                " upcoming ones.",
                _SHOW_DATE,
                includes=_SHOW_SCOPE,
            ),
        ),
        stat(
            "announced_shows",
            "Shows announced on air",
            ratio(announced, complete),
            "percent",
            explanation(
                _ANNOUNCED_FORMULA, _SHOW_DATE, includes=f"{_SHOW_SCOPE} {_COMPLETE}"
            ),
            note=f"{announced} of {complete} shows",
        ),
        _funnel_stat_table(
            "giveaway_funnel",
            '"I\'m off the mic" page visits',
            [("All visits", _funnel(visits))],
            visits_since,
        ),
    ]

    given_by_dj = Counter(_given_by(p) for p in giveaways)
    tried_by_dj = Counter(_tried_by(a) for a in attempts)
    metrics.append(
        table(
            "top_djs_given_tried",
            "Top DJs by given away plus tried",
            [
                column("dj", "DJ", link="/djs/{dj_key}"),
                column("total", "Given away + tried", "number", help=_TOTAL_HELP),
                column("given", "Given away", "number", help=_GIVEN_HELP),
                column("tried", "Tried", "number", help=_TRIED_HELP),
            ],
            sorted(
                (
                    {
                        "dj": _dj_label(k, names),
                        "dj_key": _dj_link_key(k),
                        "given": given_by_dj[k],
                        "tried": tried_by_dj[k],
                        "total": given_by_dj[k] + tried_by_dj[k],
                    }
                    for k in set(given_by_dj) | set(tried_by_dj)
                ),
                key=lambda r: -r["total"],
            ),
            explanation(
                "How often each DJ announced a giveaway on air for shows in the window,"
                " most first.",
                _SHOW_DATE,
                includes=_DJ_NAMES,
            ),
            top=TOP_ROWS,
        )
    )
    metrics.extend(_top_venue_tables(completed))
    metrics.append(_spin_match_table(db, window))
    metrics.extend(_weekday_and_time_tables(completed))
    metrics.extend(_staff_reach(db, window))
    return metrics


_VISIT_COLUMNS = [
    column(
        "visits",
        "Visits",
        "number",
        help=(
            "Loads of a show's \"I'm off the mic\" page (a reload within 10 minutes"
            " continues the same visit)."
        ),
    ),
    column(
        "given_away",
        "Given away",
        "percent",
        help="Visits in which a pass pair was given away ÷ visits.",
    ),
    column(
        "tried",
        "Tried",
        "percent",
        help='Visits in which "tried" was clicked, and nothing was given away ÷ visits.',
    ),
    column(
        "neither",
        "Neither",
        "percent",
        help='Visits with no giveaway and no "tried" click ÷ visits.',
    ),
]


def _funnel_stat_table(
    metric_id: str,
    title: str,
    groups: list[tuple[str, dict[str, int]]],
    since: Optional[date],
    label: str = "",
) -> dict:
    rows = []
    for name, counts in groups:
        row = _funnel_row(counts)
        row["group"] = name
        rows.append(row)
    cols = list(_VISIT_COLUMNS)
    if label:
        cols.insert(0, column("group", label))
    return table(
        metric_id,
        title,
        cols,
        rows,
        explanation(
            _VISIT_FORMULA,
            "Show date of the show the page is for",
            includes=_VISIT_DJ,
            excludes=_VISIT_EXCLUDES,
            data_since=since,
        ),
    )


def _spin_match_table(db: Session, window: Window) -> dict:
    counts = tracking_service.entity_event_counts(
        db,
        [SPIN_MATCH_SUGGESTED, SPIN_MATCH_GIVEAWAY],
        "show",
        _show_ids_in_window(db, window),
    )
    by = Counter()
    for c in counts:
        if c.event_type == SPIN_MATCH_SUGGESTED:
            by["suggested"] += c.count
            by[c.dimension or "ignored"] += c.count
        else:
            by["giveaways"] += c.count
    suggested = by["suggested"]
    rows = [
        {"what": "Suggested", "count": suggested, "share": None},
        {
            "what": "Clicked through",
            "count": by["clicked"],
            "share": ratio(by["clicked"], suggested),
        },
        {
            "what": "Dismissed",
            "count": by["dismissed"],
            "share": ratio(by["dismissed"], suggested),
        },
        {
            "what": "Ignored",
            "count": by["ignored"],
            "share": ratio(by["ignored"], suggested),
        },
        {
            "what": "Pass pairs given away within 2 hours",
            "count": by["giveaways"],
            "share": None,
        },
    ]
    return table(
        "spin_match_suggestions",
        "Passes suggested by the on-air popup",
        [
            column("what", ""),
            column(
                "count",
                "Count",
                "number",
                help=(
                    'Suggested: popups shown. Clicked through: the DJ clicked "Go to'
                    ' show". Dismissed: the DJ closed it with its ×. Ignored: neither;'
                    " the DJ left it alone and it went away by itself, 15 minutes after"
                    " the song started playing, or sooner if the show stopped being one"
                    " they could give away (its pairs ran out, it passed its planned"
                    " close time, or they gave one away for it), or the tab was closed."
                    " The last row: pass pairs given away for a suggested show within 2"
                    " hours of its popup."
                ),
            ),
            column("share", "Of suggested", "percent", help="Count ÷ popups suggested."),
        ],
        rows,
        explanation(
            "When a track by a show's artist plays on air, the DJ view pops up that show."
            " Each (track play, show) match counts once as suggested, however many DJ"
            " tabs show it.",
            "Show date of the suggested show",
            excludes=_VISIT_EXCLUDES,
            data_since=tracking_service.data_since(db, [SPIN_MATCH_SUGGESTED]),
        ),
    )


def _weekday_and_time_tables(completed: list[Show]) -> list[dict]:
    by_day = _utilization_by(completed, lambda s: s.show_date.weekday())
    day_rows = [
        {"weekday": WEEKDAYS[d], **_utilization_row(by_day[d])}
        for d in range(7)
        if d in by_day
    ]

    def bucket(s: Show) -> str:
        if s.show_time is None:
            return "Unknown"
        for label, start, end in SHOW_TIME_BUCKETS:
            if s.show_time >= start and (end is None or s.show_time < end):
                return label
        return "Unknown"

    by_time = _utilization_by(completed, bucket)
    order = [b[0] for b in SHOW_TIME_BUCKETS] + ["Unknown"]
    time_rows = [{"time": t, **_utilization_row(by_time[t])} for t in order if t in by_time]
    expl = f"{_SHOW_SCOPE} {_COMPLETE}"
    return [
        table(
            "utilization_by_weekday",
            "Utilization by day of the week",
            [column("weekday", "Day")] + _UTILIZATION_COLUMNS,
            day_rows,
            explanation(
                f"On-air: {_ON_AIR_FORMULA} Staff: {_STAFF_FORMULA} Grouped by the"
                " show's day of the week.",
                "Show date",
                includes=expl,
            ),
        ),
        table(
            "utilization_by_show_time",
            "Utilization by show start time",
            [column("time", "Start time")] + _UTILIZATION_COLUMNS,
            time_rows,
            explanation(
                f"On-air: {_ON_AIR_FORMULA} Staff: {_STAFF_FORMULA} Grouped by the"
                " show's start time: before 6pm, 6–9pm, after 9pm, or unknown when"
                " the show has no time.",
                "Show date",
                includes=expl,
            ),
        ),
    ]


def _staff_reach(db: Session, window: Window) -> list[dict]:
    active = [
        s
        for s in db.query(Staff).options(selectinload(Staff.statuses)).all()
        if "Active" in _staff_statuses(s)
    ]
    active_ids = {s.id for s in active}
    claims = (
        db.query(Pass)
        .join(Show, Show.id == Pass.show_id)
        .options(selectinload(Pass.show).selectinload(Show.venue))
        .filter(
            Pass.pass_type == "staff",
            Pass.status == "claimed",
            Pass.guest_of_pass_id.is_(None),
            Pass.staff_id.isnot(None),
            *_in_window(window),
        )
        .all()
    )
    with_guest = {
        g
        for (g,) in db.query(Pass.guest_of_pass_id).filter(
            Pass.guest_of_pass_id.in_([p.id for p in claims] or [-1]),
            Pass.status == "claimed",
        )
    }
    by_staff: dict[int, list[Pass]] = defaultdict(list)
    for p in claims:
        by_staff[p.staff_id].append(p)
    reached = len(active_ids & set(by_staff))
    names = (
        dict(db.query(Staff.id, Staff.name).filter(Staff.id.in_(list(by_staff))).all())
        if by_staff
        else {}
    )
    detail_columns = [
        column("show_date", "Show date", "date", help="The date of the show."),
        column("show", "Show"),
        column("venue", "Venue"),
        column(
            "guest", "+1 guest", help="Yes when they also claimed a seat for a +1 guest."
        ),
    ]
    rows = []
    for staff_id, ps in by_staff.items():
        ps.sort(key=lambda p: (p.show.show_date, p.show.event_name))
        rows.append({
            "name": names.get(staff_id, "?"),
            "claims": len(ps),
            "_details": {
                "columns": detail_columns,
                "rows": [
                    {
                        "show_date": p.show.show_date.isoformat(),
                        "show": p.show.event_name,
                        "venue": p.show.venue.name if p.show.venue else "",
                        "guest": "Yes" if p.id in with_guest else "No",
                    }
                    for p in ps
                ],
            },
        })
    rows.sort(key=lambda r: (-r["claims"], r["name"].lower()))
    claim_excludes = "+1 guest seats, and claims that were later released."
    return [
        stat(
            "staff_pass_reach",
            "Active staff who claimed a staff pass",
            ratio(reached, len(active_ids)),
            "percent",
            explanation(
                "Active staff with at least one staff pass claimed for a show in the"
                " window ÷ Active staff today.",
                _SHOW_DATE,
                includes=(
                    "Staff whose status is Active today. There's no record of who was"
                    " Active in the past, so this uses today's staff for every window."
                    " 🆕 staff can't claim staff passes, so they aren't counted."
                ),
                excludes=claim_excludes,
            ),
            note=f"{reached} of {len(active_ids)} Active staff",
        ),
        table(
            "top_staff_claimants",
            "Top staff pass claimants",
            [
                column("name", "Staff member"),
                column(
                    "claims",
                    "Staff passes claimed",
                    "number",
                    help="Staff passes they claimed for shows in the window.",
                ),
            ],
            rows,
            explanation(
                "Staff passes each staff member claimed for shows in the window, most"
                " first. Expand a row to see the shows.",
                _SHOW_DATE,
                excludes=claim_excludes,
            ),
            top=TOP_ROWS,
        ),
    ]


# ---------------------------------------------------------------------------
# Venues tab and venue page


def _window_blocks(db: Session, window: Window, venue_id: Optional[int] = None):
    """Win-limit blocks for shows in the window (at the venue)."""
    return [
        b for b in _blocks(db, _wins(db), LinkState.load(db), venue_id) if _in(window, b)
    ]


def build_venues(db: Session, window: Window, params: Params) -> list[dict]:
    today = today_pacific()
    shows = _shows_in_scope(db, window)
    completed = _completed(shows, today)
    tried_ids = {a.show_id for a in _attempts_in_window(db, window)}
    shows_by_venue: dict[int, list[Show]] = defaultdict(list)
    for s in shows:
        shows_by_venue[s.venue_id].append(s)
    completed_by_venue: dict[int, list[Show]] = defaultdict(list)
    for s in completed:
        completed_by_venue[s.venue_id].append(s)
    limits = _limit_counts(_window_blocks(db, window))
    venue_ids = set(shows_by_venue)
    venues = (
        {v.id: v for v in db.query(Venue).filter(Venue.id.in_(venue_ids)).all()}
        if venue_ids
        else {}
    )

    main_rows = []
    detail_rows = []
    for venue_id, venue in venues.items():
        vshows = shows_by_venue.get(venue_id, [])
        vdone = completed_by_venue.get(venue_id, [])
        u = _usage(vdone)
        pre, pairs = _preassigned(vshows)
        announced, complete = _announced(vdone, tried_ids)
        main_rows.append({
            "venue": venue.name,
            "venue_id": venue_id,
            "show_count": len(vshows),
            **_utilization_row(u),
            "announced": ratio(announced, complete),
            "preassigned": ratio(pre, pairs),
        })
        unused_pairs, unused_staff = _unused(vdone)
        oversub, oversub_share, _n = _lottery(db, vshows)
        joined, promoted = _alternates(db, {s.id for s in vshows})
        detail_rows.append({
            "venue": venue.name,
            "venue_id": venue_id,
            "lead_time": median(d for d in map(_lead_days, vshows) if d is not None),
            "first_giveaway": median(
                d for d in map(_first_giveaway_days, vshows) if d is not None
            ),
            "unused_pairs": unused_pairs,
            "unused_staff": unused_staff,
            "lottery": oversub,
            "lottery_share": oversub_share,
            "alternate_conversion": ratio(promoted, joined),
            "warnings": limits[venue_id]["warnings"],
            "overrides": limits[venue_id]["overrides"],
        })
    main_rows.sort(key=lambda r: venue_sort_key(r["venue"]))
    detail_rows.sort(key=lambda r: venue_sort_key(r["venue"]))
    venue_link = "/venues/{venue_id}"
    return [
        table(
            "venues",
            "Venues",
            [
                column("venue", "Venue", link=venue_link),
                column(
                    "show_count",
                    "Shows",
                    "number",
                    help="Shows with a show date in the window, including upcoming ones.",
                ),
            ]
            + _UTILIZATION_COLUMNS
            + [
                column("announced", "Announced", "percent", help=_ANNOUNCED_FORMULA),
                column(
                    "preassigned",
                    "Pre-assigned",
                    "percent",
                    help=(
                        "Pass pairs pre-assigned to a DJ, a Specialty Music Show or a"
                        " Talk & Info Show ÷ pass pairs, on every show in the window."
                    ),
                ),
            ],
            main_rows,
            explanation(
                "Each venue with shows in the window. Click a venue for its own page.",
                _SHOW_DATE,
                includes=f"{_SHOW_SCOPE} Utilization and announced: {_COMPLETE}",
                excludes=_LOW_SAMPLE_NOTE,
            ),
        ),
        table(
            "venue_details",
            "Venue lead times, leftovers and lists",
            [
                column("venue", "Venue", link=venue_link),
                column("lead_time", "Median lead time", "days", help=_LEAD_HELP),
                column(
                    "first_giveaway",
                    "Median time to first giveaway",
                    "days",
                    help=_FIRST_GIVEAWAY_HELP,
                ),
                column("unused_pairs", "Pairs unused", "number", help=_UNUSED_PAIRS_HELP),
                column(
                    "unused_staff",
                    "Staff passes unused",
                    "number",
                    help="Staff passes still available on complete shows.",
                ),
                column(
                    "lottery",
                    "Lottery entries per staff pass",
                    "number",
                    help="For shows with a staff pass lottery: entries ÷ staff passes.",
                ),
                column(
                    "lottery_share",
                    "Lottery shows oversubscribed",
                    "percent",
                    help=(
                        "Lottery shows with more entries than staff passes ÷ lottery shows."
                    ),
                ),
                column(
                    "alternate_conversion",
                    "Alternates who got a pass",
                    "percent",
                    help=(
                        "People moved from the alternate list to a staff pass ÷ people"
                        " who joined it."
                    ),
                ),
                column("warnings", "Win-limit warnings", "number", help=_WARNINGS_HELP),
                column(
                    "overrides",
                    "Win-limit overrides",
                    "number",
                    help="Warnings after which the DJ gave the caller the pass anyway.",
                ),
            ],
            detail_rows,
            explanation(
                "More about each venue's shows in the window.",
                _SHOW_DATE,
                includes=f"{_SHOW_SCOPE} Unused passes: {_COMPLETE}",
            ),
        ),
    ]


def venue_title(db: Session, params: Params) -> Optional[str]:
    venue_id = _params_venue_id(params)
    venue = db.get(Venue, venue_id) if venue_id is not None else None
    return venue.name if venue else None


def build_venue(db: Session, window: Window, params: Params) -> list[dict]:
    venue_id = _params_venue_id(params)
    venue = db.get(Venue, venue_id) if venue_id is not None else None
    if venue is None:
        return []
    today = today_pacific()
    shows = _shows_in_scope(db, window, venue_id)
    completed = _completed(shows, today)
    u = _usage(completed)
    attempts = _attempts_in_window(db, window, venue_id)
    announced, complete = _announced(completed, {a.show_id for a in attempts})
    pre, pairs = _preassigned(shows)
    low = " (low sample)" if u.shows < LOW_SAMPLE else ""
    util_includes = f"{_SHOW_SCOPE} {_COMPLETE}"

    per_month = Counter(s.show_date.strftime("%Y-%m") for s in shows)
    venue_visits = _visits(db, window, venue_id)

    lead = [d for d in map(_lead_days, shows) if d is not None]
    lead_rows = []
    for label, lo, hi in LEAD_TIME_BUCKETS:
        bucket = [
            s
            for s in completed
            if (d := _lead_days(s)) is not None and d >= lo and (hi is None or d < hi)
        ]
        bu = _usage(bucket)
        lead_rows.append(
            {"lead": label, "shows": bu.shows, "on_air": bu.on_air, "staff": bu.staff_rate}
        )
    unused_pairs, unused_staff = _unused(completed)
    oversub, oversub_share, n_lottery = _lottery(db, shows)
    joined, promoted = _alternates(db, {s.id for s in shows})
    wins = _wins(db, venue_id)
    links = LinkState.load(db)
    limits = _limit_counts(_window_blocks(db, window, venue_id))[venue_id]

    return [
        stat(
            "venue_shows",
            "Shows",
            len(shows),
            "number",
            explanation(
                "Shows at this venue with a show date in the window.",
                "Show date",
                includes=_SHOW_SCOPE,
            ),
        ),
        series(
            "venue_shows_per_month",
            "Shows per month",
            column("month", "Month"),
            [column("shows", "Shows", "number")],
            [{"month": m, "shows": per_month[m]} for m in sorted(per_month)],
            explanation(
                "Shows at this venue in each calendar month.",
                "Show date",
                includes=_SHOW_SCOPE,
            ),
            chart="bar",
        ),
        stat(
            "venue_on_air",
            "On-air utilization" + low,
            u.on_air,
            "percent",
            explanation(_ON_AIR_FORMULA, "Show date", includes=util_includes),
            note=f"{u.given} of {u.pairs} pass pairs",
        ),
        stat(
            "venue_staff",
            "Staff utilization" + low,
            u.staff_rate,
            "percent",
            explanation(_STAFF_FORMULA, "Show date", includes=util_includes),
            note=f"{u.claimed} of {u.staff} staff passes",
        ),
        stat(
            "venue_balance",
            "Utilization balance" + low,
            u.balance,
            "points",
            explanation(_BALANCE_FORMULA, "Show date", includes=util_includes),
        ),
        stat(
            "venue_announced",
            "Shows announced on air" + low,
            ratio(announced, complete),
            "percent",
            explanation(_ANNOUNCED_FORMULA, _SHOW_DATE, includes=util_includes),
            note=f"{announced} of {complete} shows",
        ),
        stat(
            "venue_preassigned",
            "Pass pairs pre-assigned",
            ratio(pre, pairs),
            "percent",
            explanation(
                "Pass pairs pre-assigned to a DJ, a Specialty Music Show or a Talk & Info"
                " Show ÷ pass pairs.",
                "Show date",
                includes=_SHOW_SCOPE,
                excludes="Pre-assignments that expired or were removed before the show.",
            ),
            note=f"{pre} of {pairs} pass pairs",
        ),
        _funnel_stat_table(
            "venue_funnel",
            '"I\'m off the mic" page visits',
            [("This venue", _funnel(venue_visits))],
            tracking_service.data_since(db, [GIVEAWAY_VISIT]),
        ),
        _repeat_winners_table(wins, window, links, "venue_repeat_winners"),
        _same_name_table(
            wins,
            window,
            {venue.id: (venue.id, venue.effective_win_frequency_days)},
            links,
            "venue_same_name",
        ),
        _who_posts_table(db, shows, venue),
        stat(
            "venue_lead_time",
            "Median lead time",
            median(lead),
            "days",
            explanation(
                _LEAD_HELP,
                "Show date",
                includes=_SHOW_SCOPE,
                excludes="Shows with no publish time (imported shows).",
            ),
        ),
        table(
            "venue_lead_time_buckets",
            "Utilization by lead time",
            [
                column(
                    "lead",
                    "Lead time",
                    help="Days from publishing the show to its show date.",
                ),
                column("shows", "Complete shows", "number", help=_COMPLETE_SHOWS_HELP),
                column("on_air", "On-air utilization", "percent", help=_ON_AIR_HELP),
                column("staff", "Staff utilization", "percent", help=_STAFF_HELP),
            ],
            lead_rows,
            explanation(
                "Complete shows grouped by days from publishing to the show date, with"
                " each group's utilization.",
                "Show date",
                includes=util_includes,
            ),
        ),
        stat(
            "venue_first_giveaway",
            "Median time to first giveaway",
            median(d for d in map(_first_giveaway_days, shows) if d is not None),
            "days",
            explanation(
                "The median number of days from publishing a show to its first pass pair"
                " given away on air.",
                "Show date",
                includes=_SHOW_SCOPE,
                excludes="Shows with no giveaways, and shows with no publish time.",
            ),
        ),
        stat(
            "venue_unused",
            "Passes unused at close",
            unused_pairs + unused_staff,
            "number",
            explanation(
                "Pass pairs and staff passes still available on complete shows.",
                "Show date",
                includes=util_includes,
            ),
            note=f"{unused_pairs} pass pairs, {unused_staff} staff passes",
        ),
        stat(
            "venue_lottery",
            "Lottery entries per staff pass",
            oversub,
            "number",
            explanation(
                "For shows with a staff pass lottery: lottery entries ÷ staff passes.",
                "Show date",
                includes=_SHOW_SCOPE,
            ),
            note=(
                f"{n_lottery} lottery shows, {oversub_share * 100:.0f}% oversubscribed"
                if oversub_share is not None
                else "No lottery shows"
            ),
        ),
        stat(
            "venue_alternates",
            "Alternates who got a pass",
            ratio(promoted, joined),
            "percent",
            explanation(
                "People moved from a show's alternate list to a staff pass ÷ people who"
                " joined the alternate list, for this venue's shows.",
                "Show date",
                includes=_SHOW_SCOPE,
            ),
            note=f"{promoted} of {joined} who joined",
        ),
        stat(
            "venue_win_limits",
            "Win-limit warnings",
            limits["warnings"],
            "number",
            explanation(
                f"{_WARNINGS_HELP} The note counts the times the DJ gave the pass anyway.",
                "Show date of the show they called for",
            ),
            note=f"{limits['overrides']} overrides",
        ),
    ]


# ---------------------------------------------------------------------------
# DJs tab and DJ page


def build_djs(db: Session, window: Window, params: Params) -> list[dict]:
    names = _dj_display_names(db)
    giveaways = _giveaways_in_window(db, window)
    attempts = _attempts_in_window(db, window)
    visits = _visits(db, window)
    given = Counter(_given_by(p) for p in giveaways)
    tried = Counter(_tried_by(a) for a in attempts)
    by_dj: dict[Optional[str], list[_Visit]] = defaultdict(list)
    for v in visits:
        by_dj[v.dj].append(v)
    rows = []
    for key in set(given) | set(tried) | set(by_dj):
        funnel = _funnel_row(_funnel(by_dj.get(key, [])))
        rows.append({
            "dj": _dj_label(key, names),
            "dj_key": _dj_link_key(key),
            "given": given[key],
            "tried_count": tried[key],
            "total": given[key] + tried[key],
            **funnel,
            "_low_sample": funnel["visits"] < LOW_SAMPLE,
        })
    rows.sort(key=lambda r: (-r["given"], -r["visits"], r["dj"].lower()))
    return [
        table(
            "djs",
            "DJs",
            [
                column("dj", "DJ", link="/djs/{dj_key}"),
                column("given", "Pass pairs given away", "number", help=_GIVEN_HELP),
                column("tried_count", "Tried", "number", help=_TRIED_HELP),
                column("total", "Given away + tried", "number", help=_TOTAL_HELP),
            ]
            + [
                {**c, "key": key, "label": label}
                for c, key, label in zip(
                    _VISIT_COLUMNS,
                    ["visits", "given_away", "tried", "neither"],
                    [
                        "Page visits",
                        "Visits: given away",
                        "Visits: tried",
                        "Visits: neither",
                    ],
                )
            ],
            rows,
            explanation(
                'Each DJ\'s giveaways, "tried" clicks and "I\'m off the mic" page'
                f" visits for shows in the window. {_VISIT_FORMULA}",
                _SHOW_DATE,
                includes=f"{_DJ_NAMES} {_VISIT_DJ}",
                excludes=(
                    f"{_VISIT_EXCLUDES} DJs with fewer than {LOW_SAMPLE} visits are marked"
                    " low sample."
                ),
                data_since=tracking_service.data_since(db, [GIVEAWAY_VISIT]),
            ),
        )
    ]


def dj_title(db: Session, params: Params) -> Optional[str]:
    key = _dj_from_params(params)
    return _dj_label(key, _dj_display_names(db))


def build_dj(db: Session, window: Window, params: Params) -> list[dict]:
    key = _dj_from_params(params)
    giveaways = [p for p in _giveaways_in_window(db, window) if _given_by(p) == key]
    attempts = [a for a in _attempts_in_window(db, window) if _tried_by(a) == key]
    visits = [v for v in _visits(db, window) if v.dj == key]
    by_venue: dict[str, Counter] = defaultdict(Counter)
    for p in giveaways:
        by_venue[p.show.venue.name]["given"] += 1
    for a in attempts:
        by_venue[a.show.venue.name]["tried"] += 1
    return [
        stat(
            "dj_given",
            "Pass pairs given away",
            len(giveaways),
            "number",
            explanation(
                "Pass pairs this DJ gave away on air for shows in the window.",
                _SHOW_DATE,
                includes=_DJ_NAMES,
            ),
        ),
        stat(
            "dj_tried",
            "Tried",
            len(attempts),
            "number",
            explanation(
                'Times this DJ clicked "tried" (a giveaway announced on-air that got no'
                " callers) for shows in the window.",
                _SHOW_DATE,
                includes=_DJ_NAMES,
            ),
        ),
        _funnel_stat_table(
            "dj_funnel",
            '"I\'m off the mic" page visits',
            [("This DJ", _funnel(visits))],
            tracking_service.data_since(db, [GIVEAWAY_VISIT]),
        ),
        table(
            "dj_by_venue",
            "By venue",
            [
                column("venue", "Venue"),
                column("given", "Given away", "number", help=_GIVEN_HELP),
                column("tried", "Tried", "number", help=_TRIED_HELP),
            ],
            sorted(
                (
                    {"venue": v, "given": c["given"], "tried": c["tried"]}
                    for v, c in by_venue.items()
                ),
                key=lambda r: -(r["given"] + r["tried"]),
            ),
            explanation(
                "This DJ's giveaways and \"tried\" clicks, by the show's venue.",
                _SHOW_DATE,
            ),
        ),
    ]


# ---------------------------------------------------------------------------
# Promotions reps tab


def build_reps(db: Session, window: Window, params: Params) -> list[dict]:
    shows = sorted(_shows_in_scope(db, window), key=lambda s: (s.show_date, s.event_name))
    creators = _creators(db, [s.id for s in shows])
    emails = set(creators.values())
    for s in shows:
        emails |= _owners_of(s)
    names = _staff_names(db, emails)
    tried = Counter(a.show_id for a in _attempts_in_window(db, window))

    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for s in shows:
        creator = creators.get(s.id, "")
        owners = _owners_of(s)
        mismatch = bool(creator) and creator not in owners
        groups[(s.show_date.strftime("%Y-%m"), creator)].append({
            "show_date": s.show_date.isoformat(),
            "show": s.event_name,
            "venue": s.venue.name if s.venue else "",
            "owners": ", ".join(sorted(names.get(e, e) for e in owners)) or "None",
            "status": s.status,
            "announced": ratio(
                sum(
                    1
                    for p in s.passes
                    if p.pass_type == "pair" and p.status == "given_away"
                )
                + tried[s.id],
                sum(1 for p in s.passes if p.pass_type == "pair"),
            ),
            "_flag": mismatch,
        })
    rows = []
    for (month, creator), show_rows in groups.items():
        rows.append({
            "month": month,
            "rep": names.get(creator, creator) if creator else "Unknown creator",
            "shows": len(show_rows),
            "not_owner": sum(1 for r in show_rows if r["_flag"]),
            "_flag": any(r["_flag"] for r in show_rows),
            "_details": {
                "columns": [
                    column("show_date", "Date", "date", help="The show date."),
                    column("show", "Show"),
                    column("venue", "Venue"),
                    column(
                        "owners",
                        "Owners",
                        help=(
                            "The promotions reps of the show's promoter, or of the venue"
                            " when the show has no promoter."
                        ),
                    ),
                    column("status", "Status", help="Published or closed."),
                    column(
                        "announced",
                        "Announced",
                        "percent",
                        help=(
                            '(Pass pairs given away + "tried" clicks) ÷ pass pairs: how'
                            " often the show was announced on air for each pair it had."
                            ' Each extra "tried" click adds to it, so it can be over'
                            " 100%."
                        ),
                    ),
                ],
                "rows": show_rows,
            },
        })
    rows.sort(key=lambda r: (r["month"], -r["shows"], r["rep"].lower()), reverse=False)
    rows.sort(key=lambda r: r["month"], reverse=True)
    return [
        *_posters_by_venue(db, shows, creators, names),
        table(
            "reps_by_month",
            "Shows by promotions rep, by month",
            [
                column("month", "Month"),
                column("rep", "Promotions rep"),
                column(
                    "shows",
                    "Shows",
                    "number",
                    help="Shows taking place that month that they created.",
                ),
                column(
                    "not_owner",
                    "Shows they don't own",
                    "number",
                    help="Of those, shows they aren't one of the owners of.",
                ),
            ],
            rows,
            explanation(
                "For each calendar month, each person who filled out the new show form for"
                " shows that took place that month, and how many. Expand a row to see the"
                " shows. A show is highlighted when its creator isn't one of its owners:"
                " the reps of the show's promoter, or of the venue when the show has no"
                " promoter.",
                "Show date",
                includes=f"{_SHOW_SCOPE} The creator comes from the audit log.",
                excludes=(
                    "Shows created before the audit log existed (or imported) are under"
                    ' "Unknown creator". Ownership is compared with today\'s reps.'
                ),
            ),
        ),
    ]


def _percent_text(count: int, total: int) -> str:
    return f"{round(100 * count / total)}%"


def _posters_by_venue(
    db: Session, shows: list[Show], creators: dict[int, str], names: dict[str, str]
) -> list[dict]:
    """Who posted each venue's shows, and the venues nobody posted shows for."""
    by_venue: dict[int, Counter] = defaultdict(Counter)
    for s in shows:
        if s.venue_id is not None:
            by_venue[s.venue_id][creators.get(s.id, "")] += 1

    def poster(email: str) -> str:
        return names.get(email, email) if email else "Unknown creator"

    venues = db.query(Venue).filter(Venue.deleted.is_(False)).all()
    rows = []
    idle = []
    for v in venues:
        counts = by_venue.get(v.id)
        if not counts:
            idle.append({"venue_id": v.id, "venue": v.name})
            continue
        total = sum(counts.values())
        ranked = sorted(counts.items(), key=lambda kv: (-kv[1], poster(kv[0]).lower()))
        row = {
            "venue_id": v.id,
            "venue": v.name,
            "shows": total,
            "posted_by": (
                poster(ranked[0][0])
                if len(ranked) == 1
                else ", ".join(f"{poster(e)} {_percent_text(n, total)}" for e, n in ranked)
            ),
        }
        if len(ranked) > 1:
            row["_details"] = {
                "columns": [
                    column("poster", "Posted by"),
                    column(
                        "shows", "Shows", "number", help="This venue's shows they posted."
                    ),
                    column(
                        "share", "Share", "percent", help="Their shows ÷ the venue's shows."
                    ),
                ],
                "rows": [
                    {"poster": poster(e), "shows": n, "share": n / total} for e, n in ranked
                ],
            }
        rows.append(row)
    rows.sort(key=lambda r: (-r["shows"], venue_sort_key(r["venue"])))
    idle.sort(key=lambda r: venue_sort_key(r["venue"]))
    venue_link = "/venues/{venue_id}"
    excludes = (
        'Shows created before the audit log existed (or imported) are under "Unknown'
        ' creator".'
    )
    return [
        table(
            "posters_by_venue",
            "Who posts each venue's shows",
            [
                column("venue", "Venue", link=venue_link),
                column(
                    "shows", "Shows", "number", help="Shows with a show date in the window."
                ),
                column(
                    "posted_by",
                    "Posted by",
                    help=(
                        "Who filled out the new show form for them, with each one's share"
                        " when there's more than one."
                    ),
                ),
            ],
            rows,
            explanation(
                "For each venue with shows in the window, who filled out the new show"
                " form for them. When more than one person did, each one's share of the"
                " venue's shows is shown; expand the row for the counts.",
                "Show date",
                includes=f"{_SHOW_SCOPE} The creator comes from the audit log.",
                excludes=excludes,
            ),
        ),
        table(
            "venues_without_shows",
            "Venues with no shows posted",
            [column("venue", "Venue", link=venue_link)],
            idle,
            explanation(
                "Venues with no published or closed shows whose show date is in the"
                " window.",
                "Show date",
                excludes="Deleted venues.",
            ),
            collapsed=True,
        ),
    ]


# ---------------------------------------------------------------------------
# Site usage tab: guest sessions


def build_usage(db: Session, window: Window, params: Params) -> list[dict]:
    counts = tracking_service.event_counts(db, [GUEST_SESSION], window.start, window.end)
    per_day: dict[date, Counter] = defaultdict(Counter)
    cells: dict[str, Counter] = {
        DJ_STUDIO_NETWORK: Counter(),
        STATION_OFFICE_NETWORK: Counter(),
    }
    for c in counts:
        per_day[c.day][c.network] += c.count
        if c.occurred_at is not None and c.network in cells:
            local = c.occurred_at.astimezone(tracking_service.PACIFIC)
            cells[c.network][(local.weekday(), local.hour)] += 1
    since = tracking_service.data_since(db, [GUEST_SESSION])
    session_rule = (
        "One session per browser tab, with a new one after 30 minutes without using"
        " the page."
    )
    return [
        series(
            "guest_sessions_per_day",
            "DJ studio and station office sessions per day",
            column("day", "Day", "date"),
            [
                column("dj_studio", "DJ studio", "number"),
                column("station_office", "Station office", "number"),
            ],
            [
                {
                    "day": d.isoformat(),
                    "dj_studio": per_day[d][DJ_STUDIO_NETWORK],
                    "station_office": per_day[d][STATION_OFFICE_NETWORK],
                }
                for d in sorted(per_day)
            ],
            explanation(
                "Sessions of the pass giveaway from the DJ studio and station office"
                f" networks without a login. {session_rule}",
                "When the session started",
                excludes="Signed-in users, who are counted by active days instead.",
                data_since=since,
            ),
        ),
        heatmap(
            "dj_studio_heatmap",
            "DJ studio sessions by hour of the week",
            [
                {"weekday": w, "hour": h, "value": n}
                for (w, h), n in cells[DJ_STUDIO_NETWORK].items()
            ],
            explanation(
                "DJ studio network sessions, by the Pacific day and hour they started."
                f" {session_rule}",
                "When the session started",
                excludes=(
                    "Sessions older than 13 months, which are only kept as daily counts."
                ),
                data_since=since,
            ),
        ),
        heatmap(
            "station_office_heatmap",
            "Station office sessions by hour of the week",
            [
                {"weekday": w, "hour": h, "value": n}
                for (w, h), n in cells[STATION_OFFICE_NETWORK].items()
            ],
            explanation(
                "Station office network sessions, by the Pacific day and hour they"
                f" started. {session_rule}",
                "When the session started",
                excludes=(
                    "Sessions older than 13 months, which are only kept as daily counts."
                ),
                data_since=since,
            ),
        ),
    ]


METRIC_GROUPS = [
    MetricGroup(id="pass_giveaway_overview", tab="overview", build=build_overview),
    MetricGroup(id="pass_giveaway_venues", tab="venues", build=build_venues),
    MetricGroup(
        id="pass_giveaway_venue", tab="venue", build=build_venue, title=venue_title
    ),
    MetricGroup(id="pass_giveaway_djs", tab="djs", build=build_djs),
    MetricGroup(id="pass_giveaway_dj", tab="dj", build=build_dj, title=dj_title),
    MetricGroup(id="pass_giveaway_winners", tab="winners", build=build_winners),
    MetricGroup(
        id="pass_giveaway_winner", tab="winner", build=build_winner, title=winner_title
    ),
    MetricGroup(id="pass_giveaway_reps", tab="reps", build=build_reps),
    MetricGroup(id="pass_giveaway_usage", tab="usage", build=build_usage),
]
