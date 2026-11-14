"""Find the DJ names typed as text that don't match a Spinitron persona or show.

The pass giveaway is moving from DJ names typed as text to Spinitron personas
and shows (docs/pass-giveaway/specs/spinitron-identity/plan.md). Before the
DJ pages switch over, every stored DJ name has to match something, or the
migration that fills in persona IDs refuses to run. This lists the names that
don't, so they can be fixed first. Matching rules are in
app/pass_giveaway/services/dj_name_matching.py.

A name that can't be matched automatically (a typo, a name two personas
share, a placeholder like "Unknown") is fixed by mapping it by hand. A
mapping applies to every row with that name, in every table.

Run from the backend/ directory with DATABASE_URL pointed at the target
database. It reads Spinitron's persona directory with SPINITRON_API_KEY
(cached for a week); --offline skips that and uses only the personas the
database already knows.

    python scripts/spinitron_identity_report.py                 # the report
    python scripts/spinitron_identity_report.py --all           # also list matched names
    python scripts/spinitron_identity_report.py map "DJ Fooo" --persona 12345
    python scripts/spinitron_identity_report.py map "Take 5" --show 3
    python scripts/spinitron_identity_report.py map "Unknown" --unattributed
    python scripts/spinitron_identity_report.py unmap "DJ Fooo"
    python scripts/spinitron_identity_report.py mappings        # list mappings

The report exits with status 1 while any name is unmatched or ambiguous, and
0 once everything matches.
"""

import argparse
import asyncio
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app.models  # noqa: E402,F401  (registers every table on Base.metadata)
from app.common.services.spinitron_service import cached_persona_names  # noqa: E402
from app.common.services.tracking_service import normalize_dj_name  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models.dj_name_mapping import DjNameMapping  # noqa: E402
from app.pass_giveaway.services.dj_name_matching import (  # noqa: E402
    AMBIGUOUS,
    UNMATCHED,
    NameDirectory,
    build_directory,
    name_uses,
)


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
            "Note: matching only the personas the database knows (staff records and"
            " the schedule cache), not Spinitron's full directory.\n"
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
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.command == "map":
            return set_mapping(db, args)
        if args.command == "unmap":
            return remove_mapping(db, args.name)
        if args.command == "mappings":
            return list_mappings(db)
        return report(db, args.offline, args.all)
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
