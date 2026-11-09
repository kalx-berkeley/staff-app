"""
KALX Staff Analytics metrics for Short Links (`/go/<slug>`). `main.py`
registers `METRIC_GROUPS`.
"""

from collections import Counter, defaultdict
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.common.services import tracking_service
from app.common.services.analytics_metrics import column, explanation, series, table
from app.common.services.analytics_registry import MetricGroup, Params
from app.common.services.analytics_window import Window, today_pacific
from app.models.short_link import ShortLink
from app.short_links.routers.redirect import SHORT_LINK_REDIRECT

RESULTS = ("redirected", "blocked_not_staff", "blocked_dj_network")


def click_counts(db: Session, days: int = 30) -> dict[int, int]:
    """Short link ID → redirects in the last *days* days (for KALX Staff Admin)."""
    today = today_pacific()
    counts: Counter = Counter()
    for c in tracking_service.event_counts(
        db, [SHORT_LINK_REDIRECT], today - timedelta(days=days - 1), today
    ):
        if c.dimension == "redirected" and c.entity_id is not None:
            counts[c.entity_id] += c.count
    return dict(counts)


def build_short_links(db: Session, window: Window, params: Params) -> list[dict]:
    counts = tracking_service.event_counts(
        db, [SHORT_LINK_REDIRECT], window.start, window.end
    )
    since = tracking_service.data_since(db, [SHORT_LINK_REDIRECT])
    slugs = dict(db.query(ShortLink.id, ShortLink.slug).all())
    only_slug = (params.get("slug") or "").lower() or None

    results: dict[int, Counter] = defaultdict(Counter)
    users: dict[int, set[str]] = defaultdict(set)
    per_day: dict[date, Counter] = defaultdict(Counter)
    for c in counts:
        if c.entity_id is None:
            continue
        slug = slugs.get(c.entity_id, f"(deleted link #{c.entity_id})")
        if only_slug and slug != only_slug:
            continue
        results[c.entity_id][c.dimension] += c.count
        if c.dimension == "redirected":
            if c.actor_email:
                users[c.entity_id].add(c.actor_email)
            per_day[c.day][slug] += c.count

    rows = []
    for link_id, r in results.items():
        rows.append({
            "slug": slugs.get(link_id, f"(deleted link #{link_id})"),
            "redirects": r["redirected"],
            "users": len(users[link_id]),
            "blocked_not_staff": r["blocked_not_staff"],
            "blocked_dj_network": r["blocked_dj_network"],
        })
    rows.sort(key=lambda row: (-row["redirects"], row["slug"]))
    expl_includes = (
        "Every attempt to follow an existing short link. Users are counted by their"
        " Google account, and names aren't shown."
    )
    top_slugs = [row["slug"] for row in rows[:5]]
    return [
        table(
            "short_links",
            "Short links" + (f": /go/{only_slug}" if only_slug else ""),
            [
                column("slug", "Short link"),
                column("redirects", "Redirects", "number"),
                column("users", "Unique users", "number"),
                column("blocked_not_staff", "Blocked: not current staff", "number"),
                column("blocked_dj_network", "Blocked: DJ studio", "number"),
            ],
            rows,
            explanation(
                "For each /go/ short link: times staff were redirected to its target, the"
                " distinct staff redirected, and attempts that were blocked because the"
                " Google account isn't current staff, or because the link was opened on a"
                " DJ studio computer, which can't sign in.",
                "When the link was followed",
                includes=expl_includes,
                excludes="Slugs that don't exist.",
                data_since=since,
            ),
        ),
        series(
            "short_link_redirects_per_day",
            "Redirects per day (top 5 links)",
            column("day", "Day", "date"),
            [column(s, f"/go/{s}", "number") for s in top_slugs],
            [
                {"day": d.isoformat(), **{s: per_day[d][s] for s in top_slugs}}
                for d in sorted(per_day)
            ],
            explanation(
                "Redirects per day for the five most-used short links in the window.",
                "When the link was followed",
                includes=expl_includes,
                data_since=since,
            ),
        ),
    ]


METRIC_GROUPS = [MetricGroup(id="short_links", tab="short_links", build=build_short_links)]
