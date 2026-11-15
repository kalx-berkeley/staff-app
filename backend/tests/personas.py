"""Helpers for giving test staff members Spinitron personas."""

from itertools import count

_ids = count(10_000)


def dj_fields(*names: str, ids: list[int] | None = None) -> dict:
    """
    Staff columns for a staff member holding personas named *names*, as the
    Airtable sync stores them.

    :param names: The persona names.
    :param ids: Their persona IDs; fresh unique ones when omitted.
    :returns: `spinitron_ids`, `dj_personas` and `dj_name`, for `Staff(**...)`.
    """
    ids = list(ids) if ids is not None else [next(_ids) for _ in names]
    personas = [{"id": pid, "name": name} for pid, name in zip(ids, names)]
    return {
        "spinitron_ids": ids or None,
        "dj_personas": personas or None,
        "dj_name": ", ".join(names) or None,
    }


def persona_id(staff, name: str) -> int:
    """The ID of *staff*'s persona named *name*."""
    return next(p["id"] for p in staff.dj_personas if p["name"] == name)
