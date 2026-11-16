"""SpecialtyShowDJ model — the DJ personas of a Specialty Music Show."""

from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import object_session, relationship
from app.database import Base
from app.models.spinitron_persona import SpinitronPersona


class SpecialtyShowDJ(Base):
    """
    One DJ member of a Specialty Music Show: a Spinitron persona.

    `dj_name` keeps the persona's name as text, which the DJ pages still read
    until they move to the schedule. `persona_id` is null only for members
    added before personas were stored whose name matched no staff persona.
    """

    __tablename__ = "specialty_show_djs"

    id = Column(Integer, primary_key=True, index=True)
    specialty_show_id = Column(Integer, ForeignKey("specialty_shows.id"), nullable=False)
    dj_name = Column(String, nullable=False, index=True)
    persona_id = Column(Integer, nullable=True, index=True)

    specialty_show = relationship("SpecialtyShow", back_populates="djs")

    @property
    def name(self) -> str:
        """The persona's current name, or the stored one if it isn't known."""
        session = object_session(self)
        if self.persona_id is not None and session is not None:
            persona = session.get(SpinitronPersona, self.persona_id)
            if persona is not None:
                return persona.name
        return self.dj_name
