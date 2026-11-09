"""
Builders for the metric dicts KALX Staff Analytics returns.

Every metric has an `id`, a `title`, a `kind` and an `explanation`, which the
page shows in the metric's ⓘ popover. The kinds are:

- ``stat``: one value, with an optional note.
- ``table``: columns and rows. A row may carry ``_low_sample`` (shown
  greyed out with a "low sample" tag), ``_flag`` (highlighted) and
  ``_details`` (a nested table, shown when the row is expanded).
- ``series``: rows with an x value and one or more series, drawn as a line or
  bar chart, with a table view.
- ``heatmap``: hour-of-week cells.

Column and value formats: ``number``, ``percent`` (a 0–1 fraction),
``points`` (percentage points, drawn as a diverging bar), ``days``,
``hours``, ``date``, ``datetime``, ``text``, ``phone``.
"""

from datetime import date
from statistics import median as _median
from typing import Any, Iterable, Optional

# Venues and DJs with fewer shows or visits than this are flagged and left out
# of rankings
LOW_SAMPLE = 3

# Top lists show this many rows before "Show all"
TOP_ROWS = 10


def explanation(
    formula: str,
    date_basis: str,
    includes: Optional[str] = None,
    excludes: Optional[str] = None,
    data_since: Optional[date] = None,
) -> dict:
    """How a metric is calculated, for its ⓘ popover."""
    return {
        "formula": formula,
        "date_basis": date_basis,
        "includes": includes,
        "excludes": excludes,
        "data_since": data_since.isoformat() if data_since else None,
    }


def column(key: str, label: str, fmt: str = "text", link: Optional[str] = None) -> dict:
    """
    A table column. *link* is a path inside the analytics site with
    ``{field}`` placeholders filled from the row, e.g. ``/venues/{venue_id}``.
    """
    return {"key": key, "label": label, "format": fmt, "link": link}


def stat(
    id: str,
    title: str,
    value: Any,
    fmt: str,
    expl: dict,
    note: Optional[str] = None,
) -> dict:
    return {
        "id": id,
        "title": title,
        "kind": "stat",
        "value": value,
        "format": fmt,
        "note": note,
        "explanation": expl,
    }


def table(
    id: str,
    title: str,
    columns: list[dict],
    rows: list[dict],
    expl: dict,
    top: Optional[int] = None,
) -> dict:
    """A table; *top* shows that many rows before "Show all"."""
    return {
        "id": id,
        "title": title,
        "kind": "table",
        "columns": columns,
        "rows": rows,
        "top": top,
        "explanation": expl,
    }


def series(
    id: str,
    title: str,
    x: dict,
    lines: list[dict],
    rows: list[dict],
    expl: dict,
    chart: str = "line",
) -> dict:
    """A chart: *x* and *lines* are columns, *chart* is ``line`` or ``bar``."""
    return {
        "id": id,
        "title": title,
        "kind": "series",
        "x": x,
        "series": lines,
        "rows": rows,
        "chart": chart,
        "explanation": expl,
    }


def heatmap(id: str, title: str, cells: list[dict], expl: dict) -> dict:
    """Hour-of-week cells: ``{"weekday": 0-6 (Monday first), "hour": 0-23, "value": n}``."""
    return {
        "id": id,
        "title": title,
        "kind": "heatmap",
        "cells": cells,
        "explanation": expl,
    }


def ratio(numerator: float, denominator: float) -> Optional[float]:
    """numerator ÷ denominator, or None when the denominator is 0."""
    return numerator / denominator if denominator else None


def median(values: Iterable[float]) -> Optional[float]:
    values = list(values)
    return _median(values) if values else None
