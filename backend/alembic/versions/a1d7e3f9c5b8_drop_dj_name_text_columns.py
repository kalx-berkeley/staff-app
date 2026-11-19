"""drop the DJ name text columns, now that every record has a persona or show

Phase 4 of docs/pass-giveaway/specs/spinitron-identity/plan.md (decision 32).
Phase 3's migration filled the persona and show columns of every record, and
since then pages show the persona's or show's current name. This drops the old
typed names:

- `passes.preassigned_dj` and `passes.given_away_by_dj`;
- `on_air_winners.given_away_by_dj`;
- `show_attempts.dj_name` and `lottery_entries.dj_name`;
- `specialty_show_djs.dj_name` (whose `persona_id` becomes required);
- `analytics_event.dj_name` and `analytics_daily_count.dj_name` (daily counts
  that differed only by DJ name are added together);
- the `dj_name_mappings` table, used only to fill the columns in phase 3.

It refuses to run, before changing anything, while any record has a DJ name
but neither a persona nor a show (which would leave it unattributed, or a
pre-assignment unassigned), listing them, unless `dj_name_mappings` maps the
name to no one. Phase 3 left none, so this is a safety net. A production deploy whose migration fails rolls back.

The downgrade adds the columns back, filled with current persona and show
names, which is as close as the names can come back.

Revision ID: a1d7e3f9c5b8
Revises: e7a3c9f5b1d2
Create Date: 2026-11-19 12:00:00.000000

"""

from typing import NamedTuple, Optional, Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "a1d7e3f9c5b8"
down_revision: Union[str, None] = "e7a3c9f5b1d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


class NameColumn(NamedTuple):
    """A DJ name text column and the identity columns that replace it."""

    table: str
    text: str
    persona: str
    # None where the name must be a persona's (music show DJs)
    show: Optional[str]
    # Whether the text column was NOT NULL (for the downgrade)
    required: bool = False


COLUMNS = [
    NameColumn(
        "passes",
        "preassigned_dj",
        "preassigned_persona_id",
        "preassigned_specialty_show_id",
    ),
    NameColumn(
        "passes",
        "given_away_by_dj",
        "given_away_persona_id",
        "given_away_specialty_show_id",
    ),
    NameColumn(
        "on_air_winners",
        "given_away_by_dj",
        "given_away_persona_id",
        "given_away_specialty_show_id",
        True,
    ),
    NameColumn("show_attempts", "dj_name", "persona_id", "specialty_show_id", True),
    NameColumn("lottery_entries", "dj_name", "persona_id", "specialty_show_id"),
    NameColumn("specialty_show_djs", "dj_name", "persona_id", None, True),
    NameColumn("analytics_event", "dj_name", "persona_id", "specialty_show_id"),
    NameColumn("analytics_daily_count", "dj_name", "persona_id", "specialty_show_id"),
]

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
    "persona_id",
    "specialty_show_id",
    "dimension",
]
_NEW_DAILY_COUNT_KEY = [c for c in _DAILY_COUNT_KEY if c != "dj_name"]


def _key(name: str) -> str:
    """Lowercase, whitespace collapsed, as `dj_name_mappings.name_key` is."""
    return " ".join(name.split()).lower()[:100]


def _unmatched(conn) -> list[str]:
    """Records with a DJ name but no persona or show, unless mapped to no one."""
    unattributed = {
        key
        for (key,) in conn.execute(
            sa.text(
                "SELECT name_key FROM dj_name_mappings"
                " WHERE persona_id IS NULL AND specialty_show_id IS NULL"
            )
        )
    }
    problems = []
    for col in COLUMNS:
        no_identity = f"{col.persona} IS NULL"
        if col.show:
            no_identity += f" AND {col.show} IS NULL"
        rows = conn.execute(
            sa.text(
                f"SELECT {col.text}, COUNT(*) FROM {col.table}"
                f" WHERE TRIM(COALESCE({col.text}, '')) != '' AND {no_identity}"
                f" GROUP BY {col.text} ORDER BY {col.text}"
            )
        ).fetchall()
        problems += [
            f"  {col.table}.{col.text} {name!r}: {count} record(s)"
            for name, count in rows
            if _key(name) not in unattributed
        ]
    return problems


def _merge_daily_counts(conn) -> None:
    """Add together the daily counts whose keys differ only by DJ name."""
    key = ", ".join(_NEW_DAILY_COUNT_KEY)
    groups = conn.execute(
        sa.text(
            "SELECT MIN(id), SUM(count), GROUP_CONCAT(id) FROM analytics_daily_count"
            f" GROUP BY {key} HAVING COUNT(*) > 1"
        )
    ).fetchall()
    for keep, total, ids in groups:
        others = [int(i) for i in str(ids).split(",") if int(i) != keep]
        conn.execute(
            sa.text("UPDATE analytics_daily_count SET count = :n WHERE id = :id"),
            {"n": total, "id": keep},
        )
        conn.execute(
            sa.text("DELETE FROM analytics_daily_count WHERE id IN :ids").bindparams(
                sa.bindparam("ids", expanding=True)
            ),
            {"ids": others},
        )


def upgrade() -> None:
    conn = op.get_bind()
    problems = _unmatched(conn)
    if problems:
        raise RuntimeError(
            f"{len(problems)} DJ name(s) have no persona or show, so dropping the"
            " DJ name columns would lose who they belong to. Credit them (for"
            " giveaways, Promotions → Admin → Giveaway Credit), then deploy again:\n"
            + "\n".join(problems)
        )

    _merge_daily_counts(conn)
    with op.batch_alter_table("analytics_daily_count") as batch:
        batch.drop_constraint("uq_analytics_daily_count_key", type_="unique")
        batch.drop_column("dj_name")
        batch.create_unique_constraint("uq_analytics_daily_count_key", _NEW_DAILY_COUNT_KEY)
    with op.batch_alter_table("specialty_show_djs") as batch:
        batch.drop_index("ix_specialty_show_djs_dj_name")
        batch.drop_column("dj_name")
        batch.alter_column("persona_id", existing_type=sa.Integer(), nullable=False)
    for col in COLUMNS:
        if col.table in ("analytics_daily_count", "specialty_show_djs"):
            continue
        with op.batch_alter_table(col.table) as batch:
            batch.drop_column(col.text)

    op.drop_table("dj_name_mappings")


def _current_name(col: NameColumn) -> str:
    """SQL for a record's current persona or show name (see `app/models/credit.py`)."""
    persona = f"(SELECT name FROM spinitron_personas WHERE id = {col.table}.{col.persona})"
    if col.show is None:
        return persona
    show = f"(SELECT name FROM specialty_shows WHERE id = {col.table}.{col.show})"
    if col.table == "lottery_entries":
        # The persona entering, or a talk show's name
        return f"COALESCE({persona}, {show})"
    return (
        f"CASE WHEN {show} IS NOT NULL AND {persona} IS NOT NULL"
        f" THEN {show} || ' (' || {persona} || ')' ELSE COALESCE({show}, {persona}) END"
    )


def downgrade() -> None:
    op.create_table(
        "dj_name_mappings",
        sa.Column("name_key", sa.String(), primary_key=True),
        sa.Column("persona_id", sa.Integer(), nullable=True),
        sa.Column(
            "specialty_show_id",
            sa.Integer(),
            sa.ForeignKey("specialty_shows.id"),
            nullable=True,
        ),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    conn = op.get_bind()
    for col in COLUMNS:
        with op.batch_alter_table(col.table) as batch:
            batch.add_column(sa.Column(col.text, sa.String(), nullable=True))
        fallback = "''" if col.required else "NULL"
        conn.execute(
            sa.text(
                f"UPDATE {col.table} SET {col.text} = COALESCE({_current_name(col)},"
                f" {fallback})"
            )
        )
        if col.required:
            with op.batch_alter_table(col.table) as batch:
                batch.alter_column(col.text, existing_type=sa.String(), nullable=False)

    # Analytics stored the name normalized
    for table in ("analytics_event", "analytics_daily_count"):
        conn.execute(sa.text(f"UPDATE {table} SET dj_name = LOWER(dj_name)"))
    with op.batch_alter_table("analytics_daily_count") as batch:
        batch.drop_constraint("uq_analytics_daily_count_key", type_="unique")
        batch.create_unique_constraint("uq_analytics_daily_count_key", _DAILY_COUNT_KEY)
    with op.batch_alter_table("specialty_show_djs") as batch:
        batch.alter_column("persona_id", existing_type=sa.Integer(), nullable=True)
        batch.create_index("ix_specialty_show_djs_dj_name", ["dj_name"])
