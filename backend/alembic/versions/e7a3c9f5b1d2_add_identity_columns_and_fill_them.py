"""add persona and show columns to giveaways, attempts and analytics, and fill every record

Phase 3 of docs/pass-giveaway/specs/spinitron-identity/plan.md (decisions 10,
11, 29, 31 and 33). Adds:

- `given_away_persona_id` and `given_away_specialty_show_id` on `passes` and
  `on_air_winners` (who a giveaway is credited to);
- `persona_id` and `specialty_show_id` on `show_attempts`, `analytics_event`
  and `analytics_daily_count`.

Then fills the persona and show columns of every record from its DJ name
text, including the pre-assignment, lottery entry and music show DJ rows that
phase 2b's migration couldn't match. The matching is the same as
`app/pass_giveaway/services/dj_name_matching.py`, with `--offline`: a mapping
in `dj_name_mappings` first, then a show of that name (not deleted), then a
persona of that name from the nightly copy of Spinitron's directory
(`spinitron_personas`), staff records and the cached schedule. It's written
out here rather than imported, so this migration keeps working once phase 4
drops the text columns.

It refuses to run, before changing anything, while any name is unmatched or
ambiguous, listing them. Fix them with `scripts/spinitron_identity_report.py`
(which reports zero misses with `--offline` exactly when this would run), then
deploy again. A production deploy whose migration fails rolls back.

Historical giveaway names aren't rewritten (decision 33): from now on a
giveaway shows its persona's or show's current name. A name mapped to no one
leaves both columns empty, and shows as "Unattributed".

Revision ID: e7a3c9f5b1d2
Revises: d6f2b8e4a0c1
Create Date: 2026-11-16 15:00:00.000000

"""

import json
from collections import defaultdict
from typing import NamedTuple, Optional, Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "e7a3c9f5b1d2"
down_revision: Union[str, None] = "d6f2b8e4a0c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


class NameColumn(NamedTuple):
    """A DJ name text column and the identity columns it fills."""

    table: str
    text: str
    persona: str
    # None where the name must be a persona's (music show DJs)
    show: Optional[str]
    # Whether the identity columns are new in this migration
    new: bool


COLUMNS = [
    NameColumn(
        "passes",
        "preassigned_dj",
        "preassigned_persona_id",
        "preassigned_specialty_show_id",
        False,
    ),
    NameColumn(
        "passes",
        "given_away_by_dj",
        "given_away_persona_id",
        "given_away_specialty_show_id",
        True,
    ),
    NameColumn(
        "on_air_winners",
        "given_away_by_dj",
        "given_away_persona_id",
        "given_away_specialty_show_id",
        True,
    ),
    NameColumn("show_attempts", "dj_name", "persona_id", "specialty_show_id", True),
    NameColumn("lottery_entries", "dj_name", "persona_id", "specialty_show_id", False),
    NameColumn("specialty_show_djs", "dj_name", "persona_id", None, False),
    NameColumn("analytics_event", "dj_name", "persona_id", "specialty_show_id", True),
    NameColumn("analytics_daily_count", "dj_name", "persona_id", "specialty_show_id", True),
]

# Tables whose new specialty show column references specialty_shows
_SHOW_FOREIGN_KEYS = {"passes", "on_air_winners", "show_attempts"}

# A daily count's unique key, before and after this migration
_DAILY_COUNT_KEY = [
    "day",
    "event_type",
    "area",
    "actor_email",
    "network",
    "entity_type",
    "entity_id",
    "dj_name",
    "dimension",
]
_NEW_DAILY_COUNT_KEY = _DAILY_COUNT_KEY[:-1] + [
    "persona_id",
    "specialty_show_id",
    "dimension",
]


def _key(name: Optional[str]) -> Optional[str]:
    """Lowercase, whitespace collapsed (`tracking_service.normalize_dj_name`)."""
    if not name:
        return None
    return " ".join(name.split()).lower()[:100] or None


def _json(value):
    if value is None or isinstance(value, (list, dict)):
        return value
    return json.loads(value)


class Match(NamedTuple):
    persona_id: Optional[int]
    show_id: Optional[int]
    # Why the name can't be matched, or None when it can
    problem: Optional[str] = None


class Directory:
    """Every persona, show and mapping a name can match."""

    def __init__(self, conn) -> None:
        names: dict[int, str] = {}
        self.staff_ids: set[int] = set()
        for dj_personas, spinitron_ids in conn.execute(
            sa.text("SELECT dj_personas, spinitron_ids FROM staff")
        ):
            for persona in _json(dj_personas) or []:
                if persona.get("id") is not None and persona.get("name"):
                    names[int(persona["id"])] = persona["name"]
                    self.staff_ids.add(int(persona["id"]))
            self.staff_ids.update(int(i) for i in _json(spinitron_ids) or [])
        for table in ("spinitron_shows", "spinitron_playlists"):
            for persona_id, dj_name in conn.execute(
                sa.text(
                    f"SELECT persona_id, dj_name FROM {table}"
                    " WHERE persona_id IS NOT NULL AND dj_name IS NOT NULL"
                )
            ):
                names.setdefault(int(persona_id), dj_name)
        for persona_id, name in conn.execute(
            sa.text("SELECT id, name FROM spinitron_personas")
        ):
            names[int(persona_id)] = name

        self.personas: dict[str, set[int]] = defaultdict(set)
        for persona_id, name in names.items():
            if _key(name):
                self.personas[_key(name)].add(persona_id)
        self.shows: dict[str, int] = {}
        for show_id, name in conn.execute(
            sa.text("SELECT id, name FROM specialty_shows WHERE NOT deleted")
        ):
            if _key(name):
                self.shows[_key(name)] = int(show_id)
        self.mappings: dict[str, tuple] = {
            key: (persona_id, show_id)
            for key, persona_id, show_id in conn.execute(
                sa.text(
                    "SELECT name_key, persona_id, specialty_show_id FROM dj_name_mappings"
                )
            )
        }

    def match(self, name: str, allow_show: bool) -> Match:
        key = _key(name)
        if key in self.mappings:
            persona_id, show_id = self.mappings[key]
            if show_id is not None and not allow_show:
                return Match(
                    None, None, "mapped to a show, but this column needs a persona"
                )
            return Match(persona_id, show_id)
        show_id = self.shows.get(key) if allow_show else None
        ids = self.personas.get(key, set())
        if show_id is not None and ids:
            return Match(None, None, "a show and a persona share this name")
        if show_id is not None:
            return Match(None, show_id)
        if len(ids) == 1:
            return Match(next(iter(ids)), None)
        if len(ids & self.staff_ids) == 1:
            return Match(next(iter(ids & self.staff_ids)), None)
        if ids:
            return Match(None, None, "several personas share this name")
        return Match(None, None, "no persona or show has this name")


def _unfilled(col: NameColumn) -> str:
    """Rows of *col* with a name and no identity yet."""
    where = f"{col.text} IS NOT NULL AND TRIM({col.text}) != ''"
    if not col.new:
        where += f" AND {col.persona} IS NULL"
        if col.show:
            where += f" AND {col.show} IS NULL"
    return where


def _matches(conn, directory: Directory) -> dict[NameColumn, dict[str, Match]]:
    """Each column's distinct unfilled names and what they match."""
    found = {}
    for col in COLUMNS:
        names = [
            name
            for (name,) in conn.execute(
                sa.text(
                    f"SELECT DISTINCT {col.text} FROM {col.table} WHERE {_unfilled(col)}"
                )
            )
        ]
        found[col] = {name: directory.match(name, col.show is not None) for name in names}
    return found


def upgrade() -> None:
    conn = op.get_bind()
    matches = _matches(conn, Directory(conn))
    problems = [
        f"  {col.table}.{col.text} {name!r}: {match.problem}"
        for col, names in matches.items()
        for name, match in sorted(names.items())
        if match.problem
    ]
    if problems:
        raise RuntimeError(
            f"{len(problems)} DJ name(s) don't match one persona or show, so persona"
            " and show IDs can't be filled in. Fix them with"
            " scripts/spinitron_identity_report.py (run with --offline, which matches"
            " the way this migration does), then deploy again:\n"
            + "\n".join(problems)
        )

    for col in COLUMNS:
        if not col.new:
            continue
        with op.batch_alter_table(col.table) as batch:
            batch.add_column(sa.Column(col.persona, sa.Integer(), nullable=True))
            if col.table in _SHOW_FOREIGN_KEYS:
                batch.add_column(
                    sa.Column(
                        col.show,
                        sa.Integer(),
                        sa.ForeignKey(
                            "specialty_shows.id", name=f"fk_{col.table}_{col.show}"
                        ),
                        nullable=True,
                    )
                )
            else:
                batch.add_column(sa.Column(col.show, sa.Integer(), nullable=True))
    for table in ("analytics_event", "analytics_daily_count"):
        with op.batch_alter_table(table) as batch:
            batch.create_index(f"ix_{table}_persona_id", ["persona_id"])
            batch.create_index(f"ix_{table}_specialty_show_id", ["specialty_show_id"])
    with op.batch_alter_table("analytics_daily_count") as batch:
        batch.drop_constraint("uq_analytics_daily_count_key", type_="unique")
        batch.create_unique_constraint("uq_analytics_daily_count_key", _NEW_DAILY_COUNT_KEY)

    for col, names in matches.items():
        sets = f"{col.persona} = :persona_id"
        if col.show:
            sets += f", {col.show} = :show_id"
        for name, match in names.items():
            if match.persona_id is None and match.show_id is None:
                continue  # mapped to no one: unattributed
            conn.execute(
                sa.text(
                    f"UPDATE {col.table} SET {sets}"
                    f" WHERE {col.text} = :name AND {_unfilled(col)}"
                ),
                {"name": name, "persona_id": match.persona_id, "show_id": match.show_id},
            )


def downgrade() -> None:
    with op.batch_alter_table("analytics_daily_count") as batch:
        batch.drop_constraint("uq_analytics_daily_count_key", type_="unique")
        batch.create_unique_constraint("uq_analytics_daily_count_key", _DAILY_COUNT_KEY)
    for table in ("analytics_daily_count", "analytics_event"):
        with op.batch_alter_table(table) as batch:
            batch.drop_index(f"ix_{table}_specialty_show_id")
            batch.drop_index(f"ix_{table}_persona_id")
    for col in reversed(COLUMNS):
        if not col.new:
            continue
        with op.batch_alter_table(col.table) as batch:
            if col.table in _SHOW_FOREIGN_KEYS:
                batch.drop_constraint(f"fk_{col.table}_{col.show}", type_="foreignkey")
            batch.drop_column(col.show)
            batch.drop_column(col.persona)
