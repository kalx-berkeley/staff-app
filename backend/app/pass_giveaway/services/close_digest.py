"""Collects what a show's close has to tell each person, so they get one email."""

import logging
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.models.staff import Staff

logger = logging.getLogger(__name__)


@dataclass
class _Intro:
    subject: str
    lines: list[str]
    short_lines: list[str]


@dataclass
class _Outcome:
    subject: str
    lines: list[str]
    subject_wins: bool


@dataclass
class _Message:
    staff: Staff
    intros: list[_Intro] = field(default_factory=list)
    outcome: _Outcome | None = None


class CloseDigest:
    """
    Builds one email per person from everything that happened during a close.

    An intro is something that happened on the way to closing, such as a lottery
    result or a promotion. An outcome says who is on the guest list. Someone with
    both gets the short form of the intro followed by the outcome. Someone with only
    an intro gets its full form, which has to make sense alone. That includes
    everyone whose outcome is being held: their intro goes out now and the outcome
    comes in a later digest, when a rep releases the emails.
    """

    def __init__(self) -> None:
        self._messages: dict[int, _Message] = {}

    def _message(self, staff: Staff) -> _Message:
        return self._messages.setdefault(staff.id, _Message(staff))

    def has_message(self, staff: Staff) -> bool:
        """Whether this close already has something to tell this person."""
        return staff.id in self._messages

    def add_intro(
        self,
        staff: Staff | None,
        subject: str,
        lines: list[str],
        short_lines: list[str] | None = None,
    ) -> None:
        if staff is None:
            return
        self._message(staff).intros.append(
            _Intro(subject, lines, short_lines if short_lines is not None else lines)
        )

    def add_outcome(
        self,
        staff: Staff | None,
        subject: str,
        lines: list[str],
        subject_wins: bool = False,
    ) -> None:
        """
        :param subject_wins: Use this subject over an intro's, for news that changes
            what the intro's subject would have someone believe.
        """
        if staff is None:
            return
        self._message(staff).outcome = _Outcome(subject, lines, subject_wins)

    @staticmethod
    def _join(sections: list[list[str]]) -> list[str]:
        lines: list[str] = []
        for section in sections:
            if lines:
                lines.append("")
            lines.extend(section)
        return lines

    def send(self, db: Session) -> None:
        """Send everyone their email. A failure for one person doesn't stop the rest."""
        from app.pass_giveaway.services.alternate_service import AlternateService

        messages, self._messages = self._messages, {}
        for message in messages.values():
            outcome = message.outcome
            if outcome is None:
                subject = message.intros[0].subject
                lines = self._join([intro.lines for intro in message.intros])
            else:
                subject = outcome.subject
                if message.intros and not outcome.subject_wins:
                    subject = message.intros[0].subject
                lines = self._join([
                    *(intro.short_lines for intro in message.intros),
                    outcome.lines,
                ])
            try:
                AlternateService._email(db, message.staff, subject, lines)
            except Exception:
                logger.error(
                    "Failed to send close email to staff %s",
                    message.staff.id,
                    exc_info=True,
                )
