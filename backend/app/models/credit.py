"""The name a giveaway, attempt or other record is credited to.

Records store who was on air as a Spinitron persona ID, a specialty show ID,
or both (a Specialty Music Show and its DJ). Pages show the persona's or
show's *current* name (decision 34 of
docs/pass-giveaway/specs/spinitron-identity/plan.md), so a renamed persona or
show is renamed everywhere. A record credited to no one is "Unattributed".
"""

from typing import Optional

from sqlalchemy.orm import Session

UNATTRIBUTED = "Unattributed"


def persona_name(session: Optional[Session], persona_id: Optional[int]) -> Optional[str]:
    """
    *persona_id*'s current name, from the nightly copy of Spinitron's
    directory, or from staff records for a persona it hasn't stored yet.
    """
    from app.models.spinitron_persona import SpinitronPersona

    if persona_id is None or session is None:
        return None
    persona = session.get(SpinitronPersona, persona_id)
    if persona is not None:
        return persona.name
    from app.common.services.spinitron_personas import persona_names

    return persona_names(session, [persona_id]).get(persona_id)


def credit_label(
    session: Optional[Session],
    persona_id: Optional[int],
    specialty_show_id: Optional[int],
) -> str:
    """
    The name to show for a record credited to *persona_id* and/or *specialty_show_id*.

    A music show slot's record names the show and its DJ, e.g. "Take Five
    (DJ Foo)". A persona whose name isn't known is "Persona #<id>"; with
    neither ID the record is "Unattributed".
    """
    from app.models.specialty_show import SpecialtyShow

    show = (
        session.get(SpecialtyShow, specialty_show_id)
        if session is not None and specialty_show_id is not None
        else None
    )
    persona = None
    if persona_id is not None:
        persona = persona_name(session, persona_id) or f"Persona #{persona_id}"
    if show is not None:
        return f"{show.name} ({persona})" if persona else show.name
    return persona or UNATTRIBUTED
