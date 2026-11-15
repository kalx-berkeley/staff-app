"""add spinitron personas and persona columns for pre-assignments

Phase 2b of docs/pass-giveaway/specs/spinitron-identity/plan.md:

- `spinitron_personas`, a local copy of Spinitron's persona directory with
  each staff persona's last playlist date (filled by the nightly sync).
- `persona_id` on the three records a picker fills:
  `passes.preassigned_persona_id`, `lottery_entries.persona_id` and
  `specialty_show_djs.persona_id`.

Existing rows get their persona from their DJ name text, matched against the
personas the database already knows (staff records and the cached schedule),
since a migration can't call Spinitron. Names are compared lowercased with
whitespace collapsed. A name several personas share counts only if exactly
one of them is a staff member's. Rows left unmatched (a persona no staff
member holds) keep a null persona until phase 3's migration fills every
record.

Revision ID: c5e1a7d3f9b2
Revises: b4c7e2d9a1f3
Create Date: 2026-11-15 18:00:00.000000

"""

import json
from collections import defaultdict
from typing import Optional, Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "c5e1a7d3f9b2"
down_revision: Union[str, None] = "b4c7e2d9a1f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _key(name: Optional[str]) -> Optional[str]:
    if name is None:
        return None
    key = " ".join(name.split()).lower()
    return key or None


def _json(value):
    if value is None or isinstance(value, (list, dict)):
        return value
    return json.loads(value)


def _persona_lookup(conn) -> dict[str, int]:
    """Normalized name -> persona ID, for names that pick out one persona."""
    names: dict[int, str] = {}
    staff_ids: set[int] = set()
    for dj_personas, spinitron_ids in conn.execute(
        sa.text("SELECT dj_personas, spinitron_ids FROM staff")
    ):
        for persona in _json(dj_personas) or []:
            if persona.get("id") is not None and persona.get("name"):
                names[int(persona["id"])] = persona["name"]
                staff_ids.add(int(persona["id"]))
        staff_ids.update(int(i) for i in _json(spinitron_ids) or [])
    for table in ("spinitron_shows", "spinitron_playlists"):
        for persona_id, dj_name in conn.execute(
            sa.text(
                f"SELECT persona_id, dj_name FROM {table}"
                " WHERE persona_id IS NOT NULL AND dj_name IS NOT NULL"
            )
        ):
            names.setdefault(int(persona_id), dj_name)

    by_key: dict[str, set[int]] = defaultdict(set)
    for persona_id, name in names.items():
        key = _key(name)
        if key:
            by_key[key].add(persona_id)
    lookup: dict[str, int] = {}
    for key, ids in by_key.items():
        if len(ids) == 1:
            lookup[key] = next(iter(ids))
        elif len(ids & staff_ids) == 1:
            lookup[key] = next(iter(ids & staff_ids))
    return lookup


def _backfill(conn, lookup: dict[str, int], select_sql: str, update_sql: str) -> None:
    for row_id, name in conn.execute(sa.text(select_sql)).fetchall():
        persona_id = lookup.get(_key(name))
        if persona_id is not None:
            conn.execute(sa.text(update_sql), {"id": row_id, "persona_id": persona_id})


def upgrade() -> None:
    op.create_table(
        "spinitron_personas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("last_playlist_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    with op.batch_alter_table("passes") as batch:
        batch.add_column(sa.Column("preassigned_persona_id", sa.Integer(), nullable=True))
    with op.batch_alter_table("lottery_entries") as batch:
        batch.add_column(sa.Column("persona_id", sa.Integer(), nullable=True))
    with op.batch_alter_table("specialty_show_djs") as batch:
        batch.add_column(sa.Column("persona_id", sa.Integer(), nullable=True))
        batch.create_index("ix_specialty_show_djs_persona_id", ["persona_id"])

    conn = op.get_bind()
    lookup = _persona_lookup(conn)
    # A pass pre-assigned to a show holds the show's name, not a persona's
    _backfill(
        conn,
        lookup,
        "SELECT id, preassigned_dj FROM passes WHERE preassigned_dj IS NOT NULL"
        " AND preassigned_specialty_show_id IS NULL",
        "UPDATE passes SET preassigned_persona_id = :persona_id WHERE id = :id",
    )
    # A talk show entry holds the show's name; a music show entry holds the
    # name of the member DJ who entered
    _backfill(
        conn,
        lookup,
        "SELECT e.id, e.dj_name FROM lottery_entries e"
        " LEFT JOIN specialty_shows s ON s.id = e.specialty_show_id"
        " WHERE e.entry_type = 'dj' AND e.dj_name IS NOT NULL"
        " AND (s.id IS NULL OR s.category != 'talk')",
        "UPDATE lottery_entries SET persona_id = :persona_id WHERE id = :id",
    )
    _backfill(
        conn,
        lookup,
        "SELECT id, dj_name FROM specialty_show_djs",
        "UPDATE specialty_show_djs SET persona_id = :persona_id WHERE id = :id",
    )


def downgrade() -> None:
    with op.batch_alter_table("specialty_show_djs") as batch:
        batch.drop_index("ix_specialty_show_djs_persona_id")
        batch.drop_column("persona_id")
    with op.batch_alter_table("lottery_entries") as batch:
        batch.drop_column("persona_id")
    with op.batch_alter_table("passes") as batch:
        batch.drop_column("preassigned_persona_id")
    op.drop_table("spinitron_personas")
