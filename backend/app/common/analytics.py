"""
KALX Staff Analytics metrics for the app as a whole: how often signed-in
staff use each sub-site. `main.py` registers `METRIC_GROUPS`.
"""

from collections import Counter, defaultdict
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.common.services import tracking_service
from app.common.services.analytics_metrics import column, explanation, series, table
from app.common.services.analytics_registry import MetricGroup, Params
from app.common.services.analytics_window import Window
from app.models.staff import Staff

ACTIVE_DAY = "active_day"

SUBSITE_NAMES = {
    "home": "Home page",
    "pass-giveaway": "Radio Pass Giveaway",
    "directory": "KALX Staff Directory",
    "workforms": "KALX Workforms",
    "admin": "KALX Staff Admin",
    "analytics": "KALX Staff Analytics",
}

_ACTIVE_DAY_RULE = (
    "An active day is a day (Pacific time) a signed-in staff member opened a page"
    " of a sub-site, counted once per person per sub-site per day."
)
_EXCLUDES = (
    "DJ studio and station office guests (see their sessions), and site admins"
    " while impersonating someone."
)


def _week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def build_usage(db: Session, window: Window, params: Params) -> list[dict]:
    counts = tracking_service.event_counts(db, [ACTIVE_DAY], window.start, window.end)
    since = tracking_service.data_since(db, [ACTIVE_DAY])

    daily: dict[date, set[str]] = defaultdict(set)
    weekly: dict[date, set[str]] = defaultdict(set)
    monthly: dict[str, set[str]] = defaultdict(set)
    by_subsite: dict[str, set[str]] = defaultdict(set)
    subsite_days: Counter = Counter()
    user_days: dict[str, set[date]] = defaultdict(set)
    for c in counts:
        if not c.actor_email:
            continue
        daily[c.day].add(c.actor_email)
        weekly[_week_start(c.day)].add(c.actor_email)
        monthly[c.day.strftime("%Y-%m")].add(c.actor_email)
        by_subsite[c.dimension or ""].add(c.actor_email)
        subsite_days[c.dimension or ""] += c.count
        user_days[c.actor_email].add(c.day)

    names = (
        dict(
            db.query(Staff.email, Staff.name).filter(Staff.email.in_(list(user_days))).all()
        )
        if user_days
        else {}
    )
    expl = explanation(
        "Distinct signed-in staff with at least one active day in each period.",
        "The day of the visit",
        includes=_ACTIVE_DAY_RULE,
        excludes=_EXCLUDES,
        data_since=since,
    )
    return [
        series(
            "users_per_day",
            "Signed-in users per day",
            column("day", "Day", "date"),
            [column("users", "Users", "number")],
            [{"day": d.isoformat(), "users": len(daily[d])} for d in sorted(daily)],
            expl,
        ),
        series(
            "users_per_week",
            "Signed-in users per week",
            column("week", "Week of", "date"),
            [column("users", "Users", "number")],
            [{"week": w.isoformat(), "users": len(weekly[w])} for w in sorted(weekly)],
            expl,
            chart="bar",
        ),
        series(
            "users_per_month",
            "Signed-in users per month",
            column("month", "Month"),
            [column("users", "Users", "number")],
            [{"month": m, "users": len(monthly[m])} for m in sorted(monthly)],
            expl,
            chart="bar",
        ),
        table(
            "users_by_subsite",
            "Use by sub-site",
            [
                column("subsite", "Sub-site"),
                column("users", "Users", "number"),
                column("active_days", "Active days", "number"),
            ],
            sorted(
                (
                    {
                        "subsite": SUBSITE_NAMES.get(s, s),
                        "users": len(by_subsite[s]),
                        "active_days": subsite_days[s],
                    }
                    for s in by_subsite
                ),
                key=lambda r: -r["active_days"],
            ),
            explanation(
                "For each sub-site, the distinct signed-in staff who used it in the window"
                " and their active days there, added up.",
                "The day of the visit",
                includes=_ACTIVE_DAY_RULE,
                excludes=_EXCLUDES,
                data_since=since,
            ),
        ),
        table(
            "users",
            "Signed-in users",
            [
                column("name", "Staff member"),
                column("days", "Active days", "number"),
                column("last_seen", "Last seen", "date"),
            ],
            sorted(
                (
                    {
                        "name": names.get(email, email),
                        "days": len(days),
                        "last_seen": max(days).isoformat(),
                    }
                    for email, days in user_days.items()
                ),
                key=lambda r: (-r["days"], r["name"].lower()),
            ),
            explanation(
                "Each signed-in staff member's active days in the window (any sub-site,"
                " counted once per day) and the last day they used the app.",
                "The day of the visit",
                includes=_ACTIVE_DAY_RULE,
                excludes=_EXCLUDES,
                data_since=since,
            ),
            top=25,
        ),
    ]


METRIC_GROUPS = [MetricGroup(id="common_usage", tab="usage", build=build_usage)]
