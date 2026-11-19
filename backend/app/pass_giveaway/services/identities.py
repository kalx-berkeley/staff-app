"""Who a pass pair can be pre-assigned to: a persona or a specialty show.

An identity is a Spinitron persona linked to a current staff member, or a
current Specialty Music Show or Talk & Info Show. This builds the choices the
pickers offer (promotions pre-assigning, staff reserving for themselves and
the DJ lottery, and a music show's DJ editor), and checks what a request
picked. See decisions 12–16 of docs/pass-giveaway/specs/spinitron-identity/plan.md.
"""

from typing import Iterable, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.auth import _is_sublist_dj, current_staff_filter, is_current_staff
from app.common.services.spinitron_personas import (
    offered_personas,
    persona_names,
    staff_persona_ids,
    staff_personas,
)
from app.models.specialty_show import SpecialtyShow
from app.models.staff import Staff
from app.pass_giveaway.schemas.pass_schema import Identity
from app.pass_giveaway.services.specialty_show_membership import (
    member_show_ids,
    require_can_reserve_for,
    require_sublist_dj,
)

PERSONA = "persona"


def _bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def show_identity(show: SpecialtyShow) -> Identity:
    """*show* as an identity."""
    return Identity(name=show.name, kind=show.category, specialty_show_id=show.id)


def current_staff_with_personas(db: Session) -> list[Staff]:
    """Current staff members (Active or 🆕) with at least one persona."""
    return [
        s
        for s in (
            db.query(Staff)
            .filter(current_staff_filter(), Staff.dj_personas.isnot(None))
            .order_by(Staff.name)
            .all()
        )
        if staff_personas(s)
    ]


def staff_identities(
    db: Session, staff: Staff, keep_ids: Iterable[int] = ()
) -> list[Identity]:
    """*staff*'s personas a picker offers (inactive ones hidden, decision 16)."""
    return [
        Identity(name=p["name"], kind=PERSONA, persona_id=p["id"], staff_name=staff.name)
        for p in offered_personas(db, staff_personas(staff), keep_ids)
    ]


def staff_persona_identities(db: Session, keep_ids: Iterable[int] = ()) -> list[Identity]:
    """Every current staff member's offered personas, sorted by name."""
    keep = list(keep_ids)
    found = [
        identity
        for staff in current_staff_with_personas(db)
        for identity in staff_identities(db, staff, keep)
    ]
    return sorted(found, key=lambda i: (i.name.lower(), i.persona_id))


def promotions_identities(db: Session) -> list[Identity]:
    """What promotions can pre-assign a pass pair to: staff personas, then shows."""
    shows = (
        db.query(SpecialtyShow)
        .filter(SpecialtyShow.current_filter())
        .order_by(SpecialtyShow.name)
        .all()
    )
    return staff_persona_identities(db) + [show_identity(s) for s in shows]


def can_reserve_as_dj(staff: Staff) -> bool:
    """Whether *staff* may reserve under their own personas (Sublist DJs)."""
    return _is_sublist_dj(staff) and bool(staff_personas(staff))


def my_identities(db: Session, staff: Staff) -> list[Identity]:
    """
    What *staff* can reserve on-air pass pairs for (or enter the DJ lottery as).

    Their own personas when they're a Sublist DJ, the music shows they're a
    DJ of (Sublist DJs only) and the talk shows they're a staff member of
    (current staff only).
    """
    identities = staff_identities(db, staff) if can_reserve_as_dj(staff) else []
    show_ids = member_show_ids(db, staff)
    if show_ids:
        shows = (
            db.query(SpecialtyShow)
            .filter(SpecialtyShow.id.in_(show_ids), SpecialtyShow.current_filter())
            .order_by(SpecialtyShow.name)
            .all()
        )
        for show in shows:
            allowed = is_current_staff(staff) if show.is_talk else _is_sublist_dj(staff)
            if allowed:
                identities.append(show_identity(show))
    return identities


def persona_holder(db: Session, persona_id: int) -> Optional[Staff]:
    """The current staff member linked to *persona_id*, if any."""
    for staff in current_staff_with_personas(db):
        if persona_id in staff_persona_ids(staff):
            return staff
    return None


def staff_persona_name(db: Session, persona_id: int) -> str:
    """
    The name of a persona linked to a current staff member.

    :raises HTTPException: 400 if no current staff member holds it.
    """
    holder = persona_holder(db, persona_id)
    if holder is None:
        raise _bad_request("That DJ persona isn't linked to a current staff member")
    return _name(db, holder, persona_id)


def current_show(db: Session, show_id: int) -> SpecialtyShow:
    """
    A current (not deleted or retired) specialty show.

    :raises HTTPException: 404 if there's no such show.
    """
    show = (
        db.query(SpecialtyShow)
        .filter(SpecialtyShow.id == show_id, SpecialtyShow.current_filter())
        .first()
    )
    if show is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Specialty Music Show or Talk & Info Show not found",
        )
    return show


def require_own_persona(staff: Staff, persona_id: int) -> None:
    """
    Raise 400 unless *persona_id* is one of *staff*'s personas.
    """
    if persona_id not in staff_persona_ids(staff):
        raise _bad_request("That isn't one of your DJ personas")


def member_persona(db: Session, show: SpecialtyShow, staff: Staff) -> Optional[dict]:
    """
    *staff*'s persona that is a DJ of music show *show*, as {"id", "name"}.

    :returns: The first such persona, or None.
    """
    member_ids = show.dj_persona_ids
    for persona in staff_personas(staff):
        if persona["id"] in member_ids:
            names = persona_names(db, [persona["id"]])
            return {"id": persona["id"], "name": names.get(persona["id"], persona["name"])}
    return None


class Reservation:
    """What a staff member is reserving for (or entering the DJ lottery as)."""

    def __init__(self, persona: Optional[dict], show: Optional[SpecialtyShow]) -> None:
        # The persona reserving, as {"id", "name"}: the chosen one, or for a
        # music show the staff member's persona that is one of its DJs. None
        # for a talk show.
        self.persona = persona
        self.show = show

    @property
    def persona_id(self) -> Optional[int]:
        return self.persona["id"] if self.persona else None

    @property
    def persona_name(self) -> Optional[str]:
        return self.persona["name"] if self.persona else None

    @property
    def name(self) -> str:
        """The show's name, or the persona's."""
        return self.show.name if self.show is not None else self.persona["name"]


def resolve_reservation(
    db: Session,
    staff: Staff,
    persona_id: Optional[int],
    specialty_show_id: Optional[int],
) -> Reservation:
    """
    Check what *staff* asked to reserve for, and that they may.

    A show (if given) wins over a persona. Without either, it's their first
    offered persona.

    :raises HTTPException: 404 for an unknown show, 403 if they may not
        reserve for it, 400 for someone else's persona or no persona at all.
    """
    show = current_show(db, specialty_show_id) if specialty_show_id is not None else None
    if show is not None and show.is_talk:
        require_can_reserve_for(db, show, staff)
        return Reservation(None, show)
    if not staff_personas(staff):
        require_sublist_dj(staff)
        raise _bad_request("You don't have a DJ persona linked to your staff profile")
    require_can_reserve_for(db, show, staff)
    if show is not None:
        return Reservation(member_persona(db, show, staff), show)
    if persona_id is None:
        persona_id = staff_identities(db, staff)[0].persona_id
    require_own_persona(staff, persona_id)
    return Reservation({"id": persona_id, "name": _name(db, staff, persona_id)}, None)


def _name(db: Session, staff: Staff, persona_id: int) -> str:
    """A persona's current name, else the one on *staff*'s record, else its ID."""
    return persona_names(db, [persona_id]).get(persona_id) or next(
        (p["name"] for p in staff_personas(staff) if p["id"] == persona_id),
        f"Persona #{persona_id}",
    )
