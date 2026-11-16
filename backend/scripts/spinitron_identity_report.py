"""Find the DJ names typed as text that don't match a Spinitron persona or show.

The pass giveaway is moving from DJ names typed as text to Spinitron personas
and shows (docs/pass-giveaway/specs/spinitron-identity/plan.md). Before the
DJ pages switch over, every stored DJ name has to match something, or the
migration that fills in persona IDs refuses to run. This lists the names that
don't, so they can be fixed first. Matching rules are in
app/pass_giveaway/services/dj_name_matching.py.

A name that can't be matched automatically (a typo, a name two personas
share, a placeholder like "Unknown") is fixed by mapping it by hand. A
mapping applies to every row with that name, in every table. A mistake can
instead be corrected where it's stored with `fix`, which changes the name in
every table (or only the --column or --show given). It shows what it would
change and asks first, and records the change in the audit log.

Run from the backend/ directory with DATABASE_URL pointed at the target
database. It reads Spinitron's persona directory with SPINITRON_API_KEY
(cached for a week); --offline skips that and uses the personas the database
already knows: the nightly copy of that directory (`spinitron_personas`),
staff records and the schedule cache. Phase 3's migration matches the same
way as --offline.

    python scripts/spinitron_identity_report.py                 # the report
    python scripts/spinitron_identity_report.py --all           # also list matched names
    python scripts/spinitron_identity_report.py map "DJ Fooo" --persona 12345
    python scripts/spinitron_identity_report.py map "Take 5" --show 3
    python scripts/spinitron_identity_report.py map "Unknown" --unattributed
    python scripts/spinitron_identity_report.py unmap "DJ Fooo"
    python scripts/spinitron_identity_report.py mappings        # list mappings
    python scripts/spinitron_identity_report.py fix "DJ Fooo" "DJ Foo"
    python scripts/spinitron_identity_report.py fix "DJ Fooo" "DJ Foo" --show 12 \\
        --column passes.given_away_by_dj --by you@example.com

The report exits with status 1 while any name is unmatched or ambiguous, and
0 once everything matches.
"""

import argparse
import asyncio
import sys
from collections import defaultdict
from pathlib import Path
from typing import Optional

from sqlalchemy import func

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app.models  # noqa: E402,F401  (registers every table on Base.metadata)
from app.common.areas import PASS_GIVEAWAY_AREA  # noqa: E402
from app.common.services.audit_service import log_event  # noqa: E402
from app.common.services.spinitron_service import cached_persona_names  # noqa: E402
from app.common.services.tracking_service import normalize_dj_name  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models.dj_name_mapping import DjNameMapping  # noqa: E402
from app.models.show import Show  # noqa: E402
from app.pass_giveaway.services.dj_name_matching import (  # noqa: E402
    AMBIGUOUS,
    UNMATCHED,
    NAME_COLUMNS,
    NameColumn,
    NameDirectory,
    build_directory,
    column_by_label,
    fix_name,
    name_uses,
)

# Columns whose rows belong to a pass giveaway show, so the report can say
# which shows a name to fix was used for
SHOW_COLUMNS = {
    "passes.preassigned_dj",
    "passes.given_away_by_dj",
    "on_air_winners.given_away_by_dj",
}


def _directory(db, offline: bool) -> NameDirectory:
    """
    Build the name directory, with Spinitron's personas unless *offline*.

    :param db: Database session.
    :param offline: Skip Spinitron.
    :returns: The directory.
    """
    personas: dict[int, str] = {}
    if not offline:
        try:
            personas = asyncio.run(cached_persona_names(db))
        except Exception as e:  # noqa: BLE001 - report and carry on offline
            print(f"Couldn't read Spinitron's personas ({e}); continuing offline.\n")
    if not personas:
        print(
            "Note: matching only the personas the database knows (the nightly copy"
            " of Spinitron's directory, staff records and the schedule cache).\n"
        )
    return build_directory(db, personas)


def _describe(directory: NameDirectory, persona_id, show_id) -> str:
    if show_id is not None:
        name, category = directory.show_info.get(show_id, ("?", "?"))
        kind = "Talk & Info Show" if category == "talk" else "Specialty Music Show"
        return f"{kind} #{show_id} ({name})"
    if persona_id is not None:
        name = directory.persona_names.get(persona_id, "name unknown")
        return f"persona #{persona_id} ({name})"
    return "no one (unattributed)"


def _shows_for(
    db,
    column: NameColumn,
    names: list[str],
    unmatched_only: bool = True,
    show_id: Optional[int] = None,
) -> list[str]:
    """
    Describe the shows whose rows in *column* hold one of *names* exactly.

    :param db: Database session.
    :param column: One of the `SHOW_COLUMNS`.
    :param names: The names as stored.
    :param unmatched_only: Leave out rows whose show ID column is set, which
        already count as matched.
    :param show_id: Only this show.
    :returns: One line per show, oldest first, e.g. "2026-12-01 Band (show #3) ×2".
    """
    model = column.model
    query = (
        db.query(Show.id, Show.event_name, Show.show_date, func.count())
        .join(model, model.show_id == Show.id)
        .filter(getattr(model, column.column).in_(names))
    )
    if unmatched_only and column.show_id_column:
        query = query.filter(getattr(model, column.show_id_column).is_(None))
    if show_id is not None:
        query = query.filter(Show.id == show_id)
    rows = query.group_by(Show.id, Show.event_name, Show.show_date).order_by(
        Show.show_date, Show.id
    )
    return [
        f"{show_date} {event_name} (show #{show_id}) ×{count}"
        for show_id, event_name, show_date, count in rows
    ]


def _spellings(db, column: NameColumn, name: str) -> list[str]:
    """
    Every value stored in *column* that is *name*, compared normalized.

    :param db: Database session.
    :param column: The column.
    :param name: The name.
    :returns: The values as stored.
    """
    key = normalize_dj_name(name)
    text = getattr(column.model, column.column)
    return [
        v
        for (v,) in db.query(text).filter(text.isnot(None)).distinct()
        if normalize_dj_name(v) == key
    ]


def report(db, offline: bool, show_all: bool) -> int:
    """
    Print the report.

    :param db: Database session.
    :param offline: Skip Spinitron.
    :param show_all: Also list the names that matched.
    :returns: Exit status: 1 while any name needs fixing, else 0.
    """
    directory = _directory(db, offline)
    uses = name_uses(db, directory)

    print(
        f"Personas known: {len(directory.persona_names)}"
        f" ({len(directory.staff_persona_ids)} linked to staff)."
        f" Shows: {len(directory.show_info)}. Mappings: {len(directory.mappings)}.\n"
    )
    totals: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for use in uses:
        totals[use.column.label][0 if use.match.resolved else 1] += use.rows
    print(f"{'Column':34} {'Matched':>9} {'To fix':>9}")
    for label, (ok, bad) in totals.items():
        print(f"{label:34} {ok:9} {bad:9}")
    print()

    # Group the names that need fixing by normalized name, across columns
    problems: dict[str, list] = defaultdict(list)
    for use in uses:
        if not use.match.resolved:
            problems[normalize_dj_name(use.name)].append(use)
    if problems:
        print(f"Names to fix ({len(problems)}):\n")
        for key in sorted(problems):
            group = problems[key]
            where = ", ".join(f"{u.column.label} ×{u.rows}" for u in group)
            match = group[0].match
            label = "AMBIGUOUS" if match.kind == AMBIGUOUS else "UNMATCHED"
            print(f'  "{group[0].name}"  [{label}]  {where}')
            print(f"      {match.reason}")
            # The same name with different capitalization is a separate use
            shows: dict[str, list[str]] = defaultdict(list)
            for use in group:
                if use.column.label in SHOW_COLUMNS:
                    shows[use.column.label] += _shows_for(db, use.column, [use.name])
            for label, lines in shows.items():
                print(f"      {label} for:")
                for line in lines:
                    print(f"        {line}")
            if match.kind == UNMATCHED:
                close = directory.suggestions(group[0].name)
                if close:
                    print(f"      close: {', '.join(close)}")
        print()
    else:
        print("Every DJ name matches a persona or a show.\n")

    if show_all:
        matched: dict[str, tuple[str, int]] = {}
        for use in uses:
            if use.match.resolved:
                key = normalize_dj_name(use.name)
                desc = _describe(
                    directory, use.match.persona_id, use.match.specialty_show_id
                )
                matched.setdefault(key, (use.name, desc))
        print(f"Matched names ({len(matched)}):\n")
        for key in sorted(matched):
            name, desc = matched[key]
            print(f'  "{name}" -> {desc}')
        print()
    return 1 if problems else 0


def set_mapping(db, args: argparse.Namespace) -> int:
    """
    Map a name to a persona, a show or no one.

    :param db: Database session.
    :param args: Parsed arguments.
    :returns: Exit status.
    """
    key = normalize_dj_name(args.name)
    if not key:
        print("The name is blank.")
        return 2
    directory = build_directory(db, {})
    if args.show is not None and args.show not in directory.show_info:
        print(f"There's no show #{args.show} (or it's deleted).")
        return 2
    mapping = db.get(DjNameMapping, key) or DjNameMapping(name_key=key)
    mapping.persona_id = args.persona
    mapping.specialty_show_id = args.show
    mapping.created_by = args.by
    db.merge(mapping)
    db.commit()
    print(f'"{args.name}" -> {_describe(directory, args.persona, args.show)}')
    if args.persona is not None and args.persona not in directory.persona_names:
        print(
            "  (The database doesn't know this persona's name; check the ID in Spinitron.)"
        )
    return 0


def remove_mapping(db, name: str) -> int:
    """
    Remove a name's mapping.

    :param db: Database session.
    :param name: The name.
    :returns: Exit status.
    """
    mapping = db.get(DjNameMapping, normalize_dj_name(name) or "")
    if mapping is None:
        print(f'"{name}" has no mapping.')
        return 2
    db.delete(mapping)
    db.commit()
    print(f'Removed the mapping for "{name}".')
    return 0


def list_mappings(db) -> int:
    """
    Print every mapping.

    :param db: Database session.
    :returns: Exit status.
    """
    directory = build_directory(db, {})
    mappings = db.query(DjNameMapping).order_by(DjNameMapping.name_key).all()
    if not mappings:
        print("No mappings.")
    for m in mappings:
        by = f"  (by {m.created_by})" if m.created_by else ""
        print(
            f'  "{m.name_key}" ->'
            f" {_describe(directory, m.persona_id, m.specialty_show_id)}{by}"
        )
    return 0


def fix(db, args: argparse.Namespace) -> int:
    """
    Change a stored DJ name in place, after showing what changes and asking.

    :param db: Database session.
    :param args: Parsed arguments.
    :returns: Exit status.
    """
    columns = None
    if args.column:
        columns = [column_by_label(label) for label in args.column]
        if None in columns:
            known = ", ".join(c.label for c in NAME_COLUMNS)
            print(f"Unknown column. The columns are: {known}")
            return 2
    if args.show is not None and db.get(Show, args.show) is None:
        print(f"There's no pass giveaway show #{args.show}.")
        return 2

    # Which shows the rows belong to, read before the names change
    before: dict[str, list[str]] = defaultdict(list)
    for col in columns or NAME_COLUMNS:
        if col.label in SHOW_COLUMNS:
            before[col.label] = _shows_for(
                db,
                col,
                _spellings(db, col, args.old),
                unmatched_only=False,
                show_id=args.show,
            )
    try:
        changed = fix_name(db, args.old, args.new, columns, args.show)
    except ValueError as e:
        print(e)
        return 2
    if not changed:
        db.rollback()
        print(f'No rows hold "{args.old}" (or they already say "{args.new}").')
        return 2

    print(f'Change "{args.old}" to "{args.new}" in:')
    for label, rows in changed.items():
        print(f"  {label} ×{rows}")
        for line in before.get(label, []):
            print(f"      {line}")
    directory = _directory(db, args.offline)
    match = directory.match(args.new)
    if match.resolved:
        desc = _describe(directory, match.persona_id, match.specialty_show_id)
        print(f'"{args.new}" matches {desc}.')
    else:
        print(f'Note: "{args.new}" doesn\'t match either: {match.reason}.')

    if not args.yes and input("Make these changes? [y/N] ").strip().lower() != "y":
        db.rollback()
        print("Nothing changed.")
        return 1
    db.commit()
    log_event(
        db,
        "dj_name_fixed",
        actor_email=args.by,
        actor_role="system",
        details={
            "old": args.old,
            "new": args.new,
            "show_id": args.show,
            "rows": changed,
            "source": "scripts/spinitron_identity_report.py",
        },
        area=PASS_GIVEAWAY_AREA,
    )
    total = sum(changed.values())
    print(f"Changed {total} row{'' if total == 1 else 's'}.")
    return 0


def main() -> int:
    """Parse arguments and run the chosen command."""
    parser = argparse.ArgumentParser(
        description=__doc__.split("\n\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--offline", action="store_true", help="Don't read Spinitron")
    parser.add_argument("--all", action="store_true", help="Also list matched names")
    commands = parser.add_subparsers(dest="command")
    map_cmd = commands.add_parser("map", help="Map a name by hand")
    map_cmd.add_argument("name", help="The DJ name as stored (case doesn't matter)")
    target = map_cmd.add_mutually_exclusive_group(required=True)
    target.add_argument("--persona", type=int, help="Spinitron persona ID")
    target.add_argument(
        "--show", type=int, help="Specialty Music Show or Talk & Info Show ID"
    )
    target.add_argument(
        "--unattributed", action="store_true", help="The name belongs to no one"
    )
    map_cmd.add_argument("--by", help="Who is making the mapping, for the record")
    unmap_cmd = commands.add_parser("unmap", help="Remove a name's mapping")
    unmap_cmd.add_argument("name")
    commands.add_parser("mappings", help="List the mappings")
    fix_cmd = commands.add_parser("fix", help="Correct a name where it's stored")
    fix_cmd.add_argument("old", help="The name as stored (case doesn't matter)")
    fix_cmd.add_argument("new", help="The corrected name")
    fix_cmd.add_argument(
        "--column",
        action="append",
        help="Only this column, e.g. passes.given_away_by_dj (repeatable)",
    )
    fix_cmd.add_argument("--show", type=int, help="Only rows for this pass giveaway show")
    fix_cmd.add_argument("--by", help="Who is making the change, for the audit log")
    fix_cmd.add_argument("--yes", action="store_true", help="Don't ask first")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.command == "map":
            return set_mapping(db, args)
        if args.command == "unmap":
            return remove_mapping(db, args.name)
        if args.command == "mappings":
            return list_mappings(db)
        if args.command == "fix":
            return fix(db, args)
        return report(db, args.offline, args.all)
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
