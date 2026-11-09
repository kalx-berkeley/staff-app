"""
The metrics KALX Staff Analytics shows.

Each sub-site describes its own metrics, and `main.py` registers them here,
so the analytics router can show every sub-site's metrics without importing
a sub-site (the same pattern as `job_registry`).

A metric group belongs to one tab of the analytics site. Its `build`
function gets the database, the time window and the page's other query
parameters (such as `venue_id`), and returns metric dicts made with
`analytics_metrics`. A group can also give the page a title, as the venue
and DJ pages do.
"""

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from app.common.services.analytics_window import Window

TABS = ("overview", "venues", "venue", "djs", "dj", "reps", "short_links", "usage")

Params = Dict[str, str]


@dataclass(frozen=True)
class MetricGroup:
    """Metrics for one tab, from one sub-site."""

    id: str
    tab: str
    build: Callable[[Session, Window, Params], List[dict]]
    # The page title, for pages about one thing (a venue, a DJ)
    title: Optional[Callable[[Session, Params], Optional[str]]] = None


_groups: Dict[str, MetricGroup] = {}


def register_metric_group(group: MetricGroup) -> None:
    """Show *group*'s metrics on its tab."""
    if group.tab not in TABS:
        raise ValueError(f"Unknown analytics tab {group.tab!r}")
    _groups[group.id] = group


def groups_for_tab(tab: str) -> List[MetricGroup]:
    """The groups registered for *tab*, in the order registered."""
    return [g for g in _groups.values() if g.tab == tab]
