"""
The Radio Pass Giveaway's metrics for KALX Staff Analytics.

`main.py` registers `METRIC_GROUPS` in `analytics_registry`. Every metric
says how it's calculated in its explanation, which the analytics page shows
in the metric's ⓘ popover, so keep the two in step when changing either.

Shared rules (spec: docs/analytics/specs/analytics-site/plan.md):

- Shows count when they're published or closed and their show date is in
  the window. Utilization only counts the ones that are also complete:
  closed, or with a show date before today.
- Activity (giveaways, attempts, visits, wins) counts by when it happened.
- A venue or DJ with fewer than `LOW_SAMPLE` shows or visits is flagged and
  left out of rankings.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Callable, Iterable, Optional
from urllib.parse import quote

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
    UNKNOWN_DJ,
    as_utc,
    normalize_dj_name,
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
from app.models.staff import Staff
from app.models.venue import Venue, venue_sort_key
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
    'A visit belongs to the DJ named in the giveaway or "tried" click, otherwise to'
    " the name in the DJ name field at the top of the page. With no name it counts as"
    ' "Unknown DJ". Names match ignoring case and spacing.'
)
_VISIT_EXCLUDES = "Promotions staff previewing the DJ view, and impersonation."
_DJ_NAMES = "DJ names match ignoring case and spacing."
_WINNERS = (
    "Winners are matched by phone number, digits only and without a leading 1. The"
    " name shown is the most recent one used with that number."
)


# ---------------------------------------------------------------------------
# Loading


def _shows_in_scope(
    db: Session,
    window: Window,
    venue_id: Optional[int] = None,
) -> list[Show]:
    q = (
        db.query(Show)
        .options(
            selectinload(Show.passes),
            selectinload(Show.venue).selectinload(Venue.owners),
            selectinload(Show.promoter).selectinload(Promoter.owners),
        )
        .filter(
            Show.status.in_(COUNTED_STATUSES),
            Show.show_date >= window.start,
            Show.show_date <= window.end,
        )
    )
    if venue_id is not None:
        q = q.filter(Show.venue_id == venue_id)
    return q.all()


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


def _dj_display_names(db: Session) -> dict[str, str]:
    """Normalized DJ name → its most common spelling in giveaways and attempts."""
    spellings: dict[str, Counter] = defaultdict(Counter)
    for (name,) in db.query(Pass.given_away_by_dj).filter(
        Pass.given_away_by_dj.isnot(None)
    ):
        key = normalize_dj_name(name)
        if key:
            spellings[key][name.strip()] += 1
    for (name,) in db.query(ShowAttempt.dj_name):
        key = normalize_dj_name(name)
        if key:
            spellings[key][name.strip()] += 1
    return {k: c.most_common(1)[0][0] for k, c in spellings.items()}


def _dj_label(key: Optional[str], names: dict[str, str]) -> str:
    if not key:
        return UNKNOWN_DJ
    return names.get(key, key)


def _dj_link_key(key: Optional[str]) -> str:
    return quote(key or UNKNOWN_DJ_KEY, safe="")


def _giveaways_in_window(db: Session, window: Window, venue_id: Optional[int] = None):
    q = (
        db.query(Pass)
        .join(Show, Show.id == Pass.show_id)
        .filter(
            Pass.pass_type == "pair",
            Pass.status == "given_away",
            Pass.given_away_at >= window.start_utc,
            Pass.given_away_at < window.end_utc,
        )
    )
    if venue_id is not None:
        q = q.filter(Show.venue_id == venue_id)
    return q.all()


def _attempts_in_window(db: Session, window: Window, venue_id: Optional[int] = None):
    q = (
        db.query(ShowAttempt)
        .join(Show, Show.id == ShowAttempt.show_id)
        .filter(
            ShowAttempt.attempted_at >= window.start_utc,
            ShowAttempt.attempted_at < window.end_utc,
        )
    )
    if venue_id is not None:
        q = q.filter(Show.venue_id == venue_id)
    return q.all()


@dataclass
class _Visit:
    show_id: Optional[int]
    dj: Optional[str]
    outcome: str
    count: int


def _visits(db: Session, window: Window) -> list[_Visit]:
    return [
        _Visit(c.entity_id, c.dj_name, c.dimension or "neither", c.count)
        for c in tracking_service.event_counts(
            db, [GIVEAWAY_VISIT], window.start, window.end
        )
    ]


def _show_venues(db: Session, show_ids: Iterable[int]) -> dict[int, int]:
    ids = {i for i in show_ids if i is not None}
    if not ids:
        return {}
    return dict(db.query(Show.id, Show.venue_id).filter(Show.id.in_(ids)).all())


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
    """The DJ page's DJ: a normalized name, or None for "Unknown DJ"."""
    key = params.get("dj", "")
    return None if key == UNKNOWN_DJ_KEY else normalize_dj_name(key)


# ---------------------------------------------------------------------------
# Utilization tables


_UTILIZATION_COLUMNS = [
    column("shows", "Complete shows", "number"),
    column("on_air", "On-air utilization", "percent"),
    column("staff", "Staff utilization", "percent"),
    column("balance", "Balance", "points"),
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
        column("shows", "Complete shows", "number"),
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
                cols + [column("value", label, "percent")],
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
    name: str
    phone: str
    email: Optional[str]
    venue_id: int
    venue: str
    show: str
    show_date: date
    dj: str
    won_at: datetime


def _wins(db: Session, venue_id: Optional[int] = None) -> list[_Win]:
    q = db.query(OnAirWinner).options(
        selectinload(OnAirWinner.show), selectinload(OnAirWinner.venue)
    )
    if venue_id is not None:
        q = q.filter(OnAirWinner.venue_id == venue_id)
    return [
        _Win(
            name=w.recipient_name,
            phone=normalize_phone(w.recipient_phone),
            email=(w.recipient_email or "").strip().lower() or None,
            venue_id=w.venue_id,
            venue=w.venue.name if w.venue else "",
            show=w.show.event_name if w.show else "",
            show_date=w.show.show_date if w.show else None,
            dj=w.given_away_by_dj,
            won_at=as_utc(w.created_at),
        )
        for w in q.all()
    ]


def _repeat_winners_table(wins: list[_Win], window: Window, metric_id: str) -> dict:
    by_phone: dict[str, list[_Win]] = defaultdict(list)
    for w in wins:
        if window.contains(w.won_at) and w.phone:
            by_phone[w.phone].append(w)
    rows = []
    for phone, ws in by_phone.items():
        if len(ws) < 2:
            continue
        ws.sort(key=lambda w: w.won_at)
        rows.append({
            "name": ws[-1].name,
            "phone": phone,
            "wins": len(ws),
            "venues": ", ".join(sorted({w.venue for w in ws})),
            "dates": ", ".join(pacific_date(w.won_at).isoformat() for w in ws),
        })
    rows.sort(key=lambda r: (-r["wins"], r["name"].lower()))
    return table(
        metric_id,
        "Top repeat on-air winners",
        [
            column("name", "Name"),
            column("phone", "Phone", "phone"),
            column("wins", "Wins", "number"),
            column("venues", "Venues"),
            column("dates", "Dates won"),
        ],
        rows,
        explanation(
            "Phone numbers with two or more on-air wins in the window, most wins first.",
            "When the pass pair was given away",
            includes=_WINNERS,
        ),
        top=TOP_ROWS,
    )


def _same_name_table(
    wins: list[_Win],
    window: Window,
    win_limits: dict[int, tuple[int, Optional[int]]],
    metric_id: str,
) -> dict:
    by_name: dict[str, list[_Win]] = defaultdict(list)
    for w in wins:
        key = normalize_person_name(w.name)
        if key:
            by_name[key].append(w)
    rows = []
    for ws in by_name.values():
        phones = {w.phone for w in ws if w.phone}
        if len(phones) < 2 or not any(window.contains(w.won_at) for w in ws):
            continue
        ws.sort(key=lambda w: w.won_at)
        flagged = _bypasses_win_limit(ws, win_limits)
        emails_by_phone: dict[str, set[str]] = defaultdict(set)
        for w in ws:
            if w.email:
                emails_by_phone[w.email].add(w.phone)
        same_email = any(len(p) > 1 for p in emails_by_phone.values())
        rows.append({
            "name": ws[-1].name,
            "phones": len(phones),
            "wins": len(ws),
            "same_venue_in_limit": "Yes" if flagged else "No",
            "same_email": "Yes" if same_email else "No",
            "_flag": flagged,
            "_details": {
                "columns": [
                    column("won", "Won", "date"),
                    column("phone", "Phone", "phone"),
                    column("email", "Email"),
                    column("show", "Show"),
                    column("show_date", "Show date", "date"),
                    column("venue", "Venue"),
                    column("dj", "DJ"),
                ],
                "rows": [
                    {
                        "won": pacific_date(w.won_at).isoformat(),
                        "phone": w.phone,
                        "email": w.email,
                        "show": w.show,
                        "show_date": w.show_date.isoformat() if w.show_date else None,
                        "venue": w.venue,
                        "dj": w.dj,
                    }
                    for w in ws
                ],
            },
        })
    rows.sort(key=lambda r: (not r["_flag"], -r["phones"], r["name"].lower()))
    return table(
        metric_id,
        "Same name, different phone numbers",
        [
            column("name", "Name"),
            column("phones", "Phone numbers", "number"),
            column("wins", "Wins", "number"),
            column("same_venue_in_limit", "Same venue or sister venue within limit"),
            column("same_email", "Same email on different numbers"),
        ],
        rows,
        explanation(
            "On-air winners whose name has two or more different phone numbers. A name is"
            " listed when it has a win in the window, and is compared with its wins at"
            " any time. It's highlighted when two of its numbers won at the same venue,"
            " or at venues sharing a win limit, within that limit (days between show"
            " dates), which is how someone could get around the limit. The same email"
            " on different numbers is stronger evidence that it's one person.",
            "When the pass pair was given away (for the window); all wins for comparison",
            includes=(
                "Names match ignoring case, spacing and punctuation, with no fuzzy"
                " matching, so two different people with the same name also appear."
                " Venues with no win limit never highlight a name."
            ),
        ),
        top=TOP_ROWS,
    )


def _bypasses_win_limit(
    ws: list[_Win], win_limits: dict[int, tuple[int, Optional[int]]]
) -> bool:
    """
    Whether two different phones won within one win limit.

    Args:
        ws: One name's wins
        win_limits: Venue ID → (the ID of the venue whose limit applies, that
            limit). Venues sharing a limit are compared as one venue.
    """
    by_family: dict[int, list[_Win]] = defaultdict(list)
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


def _repeat_share(wins: list[_Win], window: Window) -> dict:
    all_time = Counter(w.phone for w in wins if w.phone)
    in_window = [w for w in wins if window.contains(w.won_at) and w.phone]
    repeat = sum(1 for w in in_window if all_time[w.phone] > 1)
    return stat(
        "repeat_winner_share",
        "Wins going to repeat winners",
        ratio(repeat, len(in_window)),
        "percent",
        explanation(
            "On-air wins in the window that went to a phone number with more than one win"
            " at any time ÷ on-air wins in the window.",
            "When the pass pair was given away",
            includes=_WINNERS,
        ),
        note=f"{repeat} of {len(in_window)} wins",
    )


def _venue_win_limits(db: Session) -> dict[int, tuple[int, Optional[int]]]:
    """Venue ID → (the ID of the venue whose win limit applies, that limit)."""
    rows = db.query(Venue.id, Venue.parent_venue_id, Venue.win_frequency_days).all()
    own = {venue_id: days for venue_id, _, days in rows}
    return {
        venue_id: (parent_id, own.get(parent_id)) if parent_id else (venue_id, days)
        for venue_id, parent_id, days in rows
    }


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
            column("shows", "Shows", "number"),
            column("venue_owner", "As a venue owner", "number"),
            column("promoter_owner", "As the show's promoter's owner", "number"),
            column("neither", "As neither", "number"),
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


def _first_giveaway_hours(show: Show) -> Optional[float]:
    if not show.published_at:
        return None
    times = [
        as_utc(p.given_away_at)
        for p in show.passes
        if p.pass_type == "pair" and p.status == "given_away" and p.given_away_at
    ]
    if not times:
        return None
    hours = (min(times) - as_utc(show.published_at)).total_seconds() / 3600
    return hours if hours >= 0 else None


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


def _win_limit_events(db: Session, window: Window) -> dict[int, Counter]:
    """Venue ID → counts of win-limit warnings and overrides in the window."""
    out: dict[int, Counter] = defaultdict(Counter)
    rows = (
        db.query(AuditLog)
        .filter(
            AuditLog.event_type.in_(
                ["winner_frequency_warning", "venue_frequency_override"]
            ),
            AuditLog.occurred_at >= window.start_utc,
            AuditLog.occurred_at < window.end_utc,
        )
        .all()
    )
    pass_ids = [r.entity_id for r in rows if r.entity_type == "pass" and r.entity_id]
    pass_venues = (
        dict(
            db.query(Pass.id, Show.venue_id)
            .join(Show, Show.id == Pass.show_id)
            .filter(Pass.id.in_(pass_ids))
            .all()
        )
        if pass_ids
        else {}
    )
    for r in rows:
        venue_id = r.entity_id if r.entity_type == "venue" else pass_venues.get(r.entity_id)
        if venue_id is None:
            continue
        kind = "warnings" if r.event_type == "winner_frequency_warning" else "overrides"
        out[venue_id][kind] += 1
    return out


def _preassigned(shows: Iterable[Show]) -> tuple[int, int]:
    pairs = pre = 0
    for s in shows:
        for p in s.passes:
            if p.pass_type == "pair":
                pairs += 1
                if p.preassigned_dj or p.preassigned_specialty_show_id:
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
    wins = _wins(db)
    visits = _visits(db, window)
    visits_since = tracking_service.data_since(db, [GIVEAWAY_VISIT])

    metrics = [
        stat(
            "shows",
            "Shows",
            len(shows),
            "number",
            explanation(
                "Shows with a show date in the window.", "Show date", includes=_SHOW_SCOPE
            ),
        ),
        stat(
            "on_air_utilization",
            "On-air utilization",
            usage.on_air,
            "percent",
            explanation(
                _ON_AIR_FORMULA, "Show date", includes=f"{_SHOW_SCOPE} {_COMPLETE}"
            ),
            note=f"{usage.given} of {usage.pairs} pass pairs",
        ),
        stat(
            "staff_utilization",
            "Staff utilization",
            usage.staff_rate,
            "percent",
            explanation(_STAFF_FORMULA, "Show date", includes=f"{_SHOW_SCOPE} {_COMPLETE}"),
            note=f"{usage.claimed} of {usage.staff} staff passes",
        ),
        stat(
            "passes_given_away",
            "Pass pairs given away",
            len(giveaways),
            "number",
            explanation(
                "Pass pairs given away on air in the window, for any show.",
                "When the pass pair was given away",
            ),
        ),
        _funnel_stat_table(
            "giveaway_funnel",
            '"I\'m off the mic" page visits',
            [("All visits", _funnel(visits))],
            visits_since,
        ),
        _repeat_winners_table(wins, window, "top_repeat_winners"),
        _repeat_share(wins, window),
        _same_name_table(wins, window, _venue_win_limits(db), "same_name_different_phones"),
    ]

    given_by_dj = Counter(normalize_dj_name(p.given_away_by_dj) for p in giveaways)
    tried_by_dj = Counter(normalize_dj_name(a.dj_name) for a in attempts)
    metrics.append(
        table(
            "top_djs_given",
            "Top DJs by pass pairs given away",
            [
                column("dj", "DJ", link="/djs/{dj_key}"),
                column("given", "Given away", "number"),
            ],
            sorted(
                (
                    {"dj": _dj_label(k, names), "dj_key": _dj_link_key(k), "given": n}
                    for k, n in given_by_dj.items()
                ),
                key=lambda r: -r["given"],
            ),
            explanation(
                "Pass pairs each DJ gave away in the window, most first.",
                "When the pass pair was given away",
                includes=_DJ_NAMES,
            ),
            top=TOP_ROWS,
        )
    )
    combined_keys = set(given_by_dj) | set(tried_by_dj)
    metrics.append(
        table(
            "top_djs_given_tried",
            "Top DJs by given away plus tried",
            [
                column("dj", "DJ", link="/djs/{dj_key}"),
                column("total", "Given away + tried", "number"),
                column("given", "Given away", "number"),
                column("tried", "Tried", "number"),
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
                    for k in combined_keys
                ),
                key=lambda r: -r["total"],
            ),
            explanation(
                'Pass pairs each DJ gave away plus the times they clicked "tried" (a'
                " failed on-air giveaway attempt) in the window, most first.",
                "When it happened",
                includes=_DJ_NAMES,
            ),
            top=TOP_ROWS,
        )
    )
    metrics.extend(_top_venue_tables(completed))
    metrics.append(_spin_match_table(db, window))
    metrics.extend(_weekday_and_time_tables(completed))
    metrics.append(_promoter_table(completed))
    metrics.extend(_staff_reach(db, window))
    return metrics


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
    cols = [
        column("visits", "Visits", "number"),
        column("given_away", "Given away", "percent"),
        column("tried", "Tried", "percent"),
        column("neither", "Neither", "percent"),
    ]
    if label:
        cols.insert(0, column("group", label))
    return table(
        metric_id,
        title,
        cols,
        rows,
        explanation(
            _VISIT_FORMULA,
            "When the visit started",
            includes=_VISIT_DJ,
            excludes=_VISIT_EXCLUDES,
            data_since=since,
        ),
    )


def _spin_match_table(db: Session, window: Window) -> dict:
    counts = tracking_service.event_counts(
        db, [SPIN_MATCH_SUGGESTED, SPIN_MATCH_GIVEAWAY], window.start, window.end
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
            column("count", "Count", "number"),
            column("share", "Of suggested", "percent"),
        ],
        rows,
        explanation(
            "When a track by a show's artist plays on air, the DJ view pops up that show."
            " Each (track play, show) match counts once as suggested, however many DJ"
            " tabs show it. Clicked through and dismissed are what the DJ did with it;"
            " ignored is neither. The last row counts pass pairs given away for a"
            " suggested show within 2 hours of its popup.",
            "When the popup was first shown",
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


def _promoter_table(completed: list[Show]) -> dict:
    by_promoter = _utilization_by(
        (s for s in completed if s.promoter is not None), lambda s: s.promoter
    )
    rows = sorted(
        ({"promoter": p.name, **_utilization_row(u)} for p, u in by_promoter.items()),
        key=lambda r: r["promoter"].lower(),
    )
    return table(
        "utilization_by_promoter",
        "Utilization by promoter",
        [column("promoter", "Promoter")] + _UTILIZATION_COLUMNS,
        rows,
        explanation(
            f"On-air: {_ON_AIR_FORMULA} Staff: {_STAFF_FORMULA} Balance:"
            f" {_BALANCE_FORMULA}",
            "Show date",
            includes=f"Shows with their own promoter. {_SHOW_SCOPE} {_COMPLETE}",
            excludes=(
                f"Promoters with fewer than {LOW_SAMPLE} complete shows are marked low"
                " sample."
            ),
        ),
    )


def _staff_reach(db: Session, window: Window) -> list[dict]:
    active = [
        s
        for s in db.query(Staff).options(selectinload(Staff.statuses)).all()
        if "Active" in _staff_statuses(s)
    ]
    active_ids = {s.id for s in active}
    claims = (
        db.query(Pass)
        .filter(
            Pass.pass_type == "staff",
            Pass.status == "claimed",
            Pass.guest_of_pass_id.is_(None),
            Pass.staff_id.isnot(None),
            Pass.claimed_at >= window.start_utc,
            Pass.claimed_at < window.end_utc,
        )
        .all()
    )
    by_staff = Counter(p.staff_id for p in claims)
    reached = len(active_ids & set(by_staff))
    names = (
        dict(db.query(Staff.id, Staff.name).filter(Staff.id.in_(list(by_staff))).all())
        if by_staff
        else {}
    )
    return [
        stat(
            "staff_pass_reach",
            "Active staff who claimed a staff pass",
            ratio(reached, len(active_ids)),
            "percent",
            explanation(
                "Active staff with at least one staff pass claimed in the window ÷ Active"
                " staff today.",
                "When the staff pass was claimed",
                includes=(
                    "Staff whose status is Active today. There's no record of who was"
                    " Active in the past, so this uses today's staff for every window."
                    " 🆕 staff can't claim staff passes, so they aren't counted."
                ),
                excludes="+1 guest seats, and claims that were later released.",
            ),
            note=f"{reached} of {len(active_ids)} Active staff",
        ),
        table(
            "top_staff_claimants",
            "Top staff pass claimants",
            [
                column("name", "Staff member"),
                column("claims", "Staff passes claimed", "number"),
            ],
            sorted(
                ({"name": names.get(i, "?"), "claims": n} for i, n in by_staff.items()),
                key=lambda r: -r["claims"],
            ),
            explanation(
                "Staff passes each staff member claimed in the window, most first.",
                "When the staff pass was claimed",
                excludes="+1 guest seats, and claims that were later released.",
            ),
            top=TOP_ROWS,
        ),
    ]


# ---------------------------------------------------------------------------
# Venues tab and venue page


def build_venues(db: Session, window: Window, params: Params) -> list[dict]:
    today = today_pacific()
    shows = _shows_in_scope(db, window)
    completed = _completed(shows, today)
    giveaways = _giveaways_in_window(db, window)
    attempts = _attempts_in_window(db, window)
    gives = Counter(p.show.venue_id for p in giveaways)
    tries = Counter(a.show.venue_id for a in attempts)
    shows_by_venue: dict[int, list[Show]] = defaultdict(list)
    for s in shows:
        shows_by_venue[s.venue_id].append(s)
    completed_by_venue: dict[int, list[Show]] = defaultdict(list)
    for s in completed:
        completed_by_venue[s.venue_id].append(s)
    win_limits = _win_limit_events(db, window)
    venue_ids = set(shows_by_venue) | set(gives) | set(tries)
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
        main_rows.append({
            "venue": venue.name,
            "venue_id": venue_id,
            "show_count": len(vshows),
            **_utilization_row(u),
            "attempts": tries[venue_id],
            "given_away": gives[venue_id],
            "attempts_per_giveaway": ratio(tries[venue_id], gives[venue_id]),
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
                h for h in map(_first_giveaway_hours, vshows) if h is not None
            ),
            "unused_pairs": unused_pairs,
            "unused_staff": unused_staff,
            "lottery": oversub,
            "lottery_share": oversub_share,
            "alternate_conversion": ratio(promoted, joined),
            "warnings": win_limits[venue_id]["warnings"],
            "overrides": win_limits[venue_id]["overrides"],
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
                column("show_count", "Shows", "number"),
            ]
            + _UTILIZATION_COLUMNS
            + [
                column("attempts_per_giveaway", "Attempts per giveaway", "number"),
                column("preassigned", "Pre-assigned", "percent"),
            ],
            main_rows,
            explanation(
                "Shows: shows with a show date in the window. On-air:"
                f" {_ON_AIR_FORMULA} Staff: {_STAFF_FORMULA} Balance: {_BALANCE_FORMULA}"
                ' Attempts per giveaway: "tried" clicks ÷ pass pairs given away, both by'
                " when they happened. Pre-assigned: pass pairs pre-assigned to a DJ or"
                " specialty show ÷ pass pairs.",
                "Show date (attempts per giveaway: when it happened)",
                includes=f"{_SHOW_SCOPE} Utilization: {_COMPLETE}",
                excludes=_LOW_SAMPLE_NOTE,
            ),
        ),
        table(
            "venue_details",
            "Venue lead times, leftovers and lists",
            [
                column("venue", "Venue", link=venue_link),
                column("lead_time", "Median lead time", "days"),
                column("first_giveaway", "Median time to first giveaway", "hours"),
                column("unused_pairs", "Pairs unused", "number"),
                column("unused_staff", "Staff passes unused", "number"),
                column("lottery", "Lottery entries per staff pass", "number"),
                column("lottery_share", "Lottery shows oversubscribed", "percent"),
                column("alternate_conversion", "Alternates who got a pass", "percent"),
                column("warnings", "Win-limit warnings", "number"),
                column("overrides", "Win-limit overrides", "number"),
            ],
            detail_rows,
            explanation(
                "Lead time: days from publishing a show to its show date. Time to first"
                " giveaway: hours from publishing to the first pass pair given away."
                " Unused: passes still available on complete shows. Lottery: staff lottery"
                " entries ÷ staff passes, and the share of lottery shows with more entries"
                " than staff passes. Alternates: people moved from the alternate list to a"
                " pass ÷ people who joined it. Win-limit warnings: a DJ was told a caller"
                " won at this venue too recently; overrides: the DJ gave the pass anyway.",
                "Show date (win-limit warnings and overrides: when they happened)",
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
    giveaways = _giveaways_in_window(db, window, venue_id)
    attempts = _attempts_in_window(db, window, venue_id)
    pre, pairs = _preassigned(shows)
    low = " (low sample)" if u.shows < LOW_SAMPLE else ""
    util_includes = f"{_SHOW_SCOPE} {_COMPLETE}"

    per_month = Counter(s.show_date.strftime("%Y-%m") for s in shows)
    visits = _visits(db, window)
    venues_of = _show_venues(db, (v.show_id for v in visits))
    venue_visits = [v for v in visits if venues_of.get(v.show_id) == venue_id]

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
    limits = _win_limit_events(db, window)[venue_id]
    wins = _wins(db, venue_id)

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
            "venue_attempts",
            "Attempts per giveaway",
            ratio(len(attempts), len(giveaways)),
            "number",
            explanation(
                'Times a DJ clicked "tried" (a failed on-air giveaway attempt) ÷ pass'
                " pairs given away, for this venue's shows.",
                "When it happened",
            ),
            note=f"{len(attempts)} attempts, {len(giveaways)} given away",
        ),
        stat(
            "venue_preassigned",
            "Pass pairs pre-assigned",
            ratio(pre, pairs),
            "percent",
            explanation(
                "Pass pairs pre-assigned to a DJ or specialty show ÷ pass pairs.",
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
        _repeat_winners_table(wins, window, "venue_repeat_winners"),
        _same_name_table(
            wins,
            window,
            {venue.id: (venue.id, venue.effective_win_frequency_days)},
            "venue_same_name",
        ),
        _who_posts_table(db, shows, venue),
        stat(
            "venue_lead_time",
            "Median lead time",
            median(lead),
            "days",
            explanation(
                "The median number of days from publishing a show to its show date.",
                "Show date",
                includes=_SHOW_SCOPE,
                excludes="Shows with no publish time (imported shows).",
            ),
        ),
        table(
            "venue_lead_time_buckets",
            "Utilization by lead time",
            [
                column("lead", "Lead time"),
                column("shows", "Complete shows", "number"),
                column("on_air", "On-air utilization", "percent"),
                column("staff", "Staff utilization", "percent"),
            ],
            lead_rows,
            explanation(
                "Complete shows grouped by days from publishing to the show date, with"
                f" each group's utilization. On-air: {_ON_AIR_FORMULA} Staff:"
                f" {_STAFF_FORMULA}",
                "Show date",
                includes=util_includes,
            ),
        ),
        stat(
            "venue_first_giveaway",
            "Median time to first giveaway",
            median(h for h in map(_first_giveaway_hours, shows) if h is not None),
            "hours",
            explanation(
                "The median number of hours from publishing a show to its first pass pair"
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
                "Times a DJ was warned that a caller won at this venue more recently than"
                " its win limit allows, and (in the note) times the DJ gave the pass"
                " anyway.",
                "When it happened",
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
    given = Counter(normalize_dj_name(p.given_away_by_dj) for p in giveaways)
    tried = Counter(normalize_dj_name(a.dj_name) for a in attempts)
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
                column("given", "Pass pairs given away", "number"),
                column("tried_count", "Tried", "number"),
                column("visits", "Page visits", "number"),
                column("given_away", "Visits: given away", "percent"),
                column("tried", "Visits: tried", "percent"),
                column("neither", "Visits: neither", "percent"),
            ],
            rows,
            explanation(
                'Given away and tried: pass pairs the DJ gave away and "tried" clicks in'
                f" the window. Visits: {_VISIT_FORMULA}",
                "When it happened",
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
    giveaways = [
        p
        for p in _giveaways_in_window(db, window)
        if normalize_dj_name(p.given_away_by_dj) == key
    ]
    attempts = [
        a for a in _attempts_in_window(db, window) if normalize_dj_name(a.dj_name) == key
    ]
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
                "Pass pairs this DJ gave away on air in the window.",
                "When the pass pair was given away",
                includes=_DJ_NAMES,
            ),
        ),
        stat(
            "dj_tried",
            "Tried",
            len(attempts),
            "number",
            explanation(
                'Times this DJ clicked "tried" (a failed on-air giveaway attempt) in the'
                " window.",
                "When it happened",
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
                column("given", "Given away", "number"),
                column("tried", "Tried", "number"),
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
                "When it happened",
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
                    column("show_date", "Date", "date"),
                    column("show", "Show"),
                    column("venue", "Venue"),
                    column("owners", "Owners"),
                    column("status", "Status"),
                ],
                "rows": show_rows,
            },
        })
    rows.sort(key=lambda r: (r["month"], -r["shows"], r["rep"].lower()), reverse=False)
    rows.sort(key=lambda r: r["month"], reverse=True)
    return [
        table(
            "reps_by_month",
            "Shows by promotions rep, by month",
            [
                column("month", "Month"),
                column("rep", "Promotions rep"),
                column("shows", "Shows", "number"),
                column("not_owner", "Shows they don't own", "number"),
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
        )
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
    MetricGroup(id="pass_giveaway_reps", tab="reps", build=build_reps),
    MetricGroup(id="pass_giveaway_usage", tab="usage", build=build_usage),
]
