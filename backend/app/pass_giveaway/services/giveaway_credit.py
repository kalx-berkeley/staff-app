"""Who promotions credit a giveaway to, picked rather than typed.

Promotions pick a persona or a show with the decision 12 picker
(`identities.promotions_identities`) when they enter winners on the show form
or re-credit a giveaway in Promotions → Admin (decision 28 of
docs/pass-giveaway/specs/spinitron-identity/plan.md). Neither is a giveaway
made on air, so the credit is one or the other, or no one (unattributed).
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.common.areas import PASS_GIVEAWAY_AREA
from app.common.services import audit_service
from app.models.pass_model import Pass
from app.models.show import Show
from app.pass_giveaway.services.identities import current_show, staff_persona_name


@dataclass(frozen=True)
class Credit:
    """A checked credit: a persona, a show, or neither."""

    persona_id: Optional[int] = None
    specialty_show_id: Optional[int] = None
    # The persona's or show's name, for the old DJ name text column
    name: Optional[str] = None


def check_credit(
    db: Session, persona_id: Optional[int], specialty_show_id: Optional[int]
) -> Credit:
    """
    Check a picked credit: a persona linked to a current staff member, or a
    current specialty show, or neither (unattributed). A show wins over a
    persona.

    :raises HTTPException: 400 for a persona no current staff member holds,
        404 for an unknown or retired show.
    """
    if specialty_show_id is not None:
        show = current_show(db, specialty_show_id)
        return Credit(specialty_show_id=show.id, name=show.name)
    if persona_id is not None:
        return Credit(persona_id=persona_id, name=staff_persona_name(db, persona_id))
    return Credit()


def apply_credit(pass_item: Pass, credit: Credit) -> None:
    """Credit a given-away pair (and its on-air winner) to *credit* (no commit)."""
    pass_item.given_away_persona_id = credit.persona_id
    pass_item.given_away_specialty_show_id = credit.specialty_show_id
    pass_item.given_away_by_dj = credit.name
    winner = pass_item.on_air_winner
    if winner is not None:
        winner.given_away_persona_id = credit.persona_id
        winner.given_away_specialty_show_id = credit.specialty_show_id
        winner.given_away_by_dj = credit.name or ""


def giveaways(db: Session, unattributed_only: bool, days: int) -> list[Pass]:
    """
    Pass pairs given away in the last *days* days, newest first; with
    *unattributed_only*, only those credited to no one.
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)
    query = (
        db.query(Pass)
        .join(Show, Pass.show_id == Show.id)
        .filter(
            Pass.pass_type == "pair",
            Pass.status == "given_away",
            Pass.given_away_at >= since.replace(tzinfo=None),
            Show.status != "deleted",
        )
    )
    if unattributed_only:
        query = query.filter(
            Pass.given_away_persona_id.is_(None),
            Pass.given_away_specialty_show_id.is_(None),
        )
    return query.order_by(Pass.given_away_at.desc(), Pass.id.desc()).all()


def recredit(db: Session, pass_item: Pass, credit: Credit, actor_email: str) -> Pass:
    """
    Re-credit a giveaway, and record the change in the audit log.

    :raises ValueError: If *pass_item* isn't a given-away pass pair.
    """
    if pass_item.pass_type != "pair" or pass_item.status != "given_away":
        raise ValueError("Only a given-away pass pair can be re-credited")
    before = {
        "dj": pass_item.given_away_by,
        "persona_id": pass_item.given_away_persona_id,
        "specialty_show_id": pass_item.given_away_specialty_show_id,
    }
    apply_credit(pass_item, credit)
    db.commit()
    db.refresh(pass_item)
    audit_service.log_event(
        db,
        event_type="giveaway_recredited",
        area=PASS_GIVEAWAY_AREA,
        actor_email=actor_email,
        actor_role="promotions",
        entity_type="pass",
        entity_id=pass_item.id,
        details={
            "show_id": pass_item.show_id,
            "before": before,
            "after": {
                "dj": pass_item.given_away_by,
                "persona_id": credit.persona_id,
                "specialty_show_id": credit.specialty_show_id,
            },
        },
    )
    return pass_item
