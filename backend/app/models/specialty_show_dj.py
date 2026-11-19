"""SpecialtyShowDJ model — the DJ personas of a Specialty Music Show."""

from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import object_session, relationship
from app.database import Base
from app.models.credit import persona_name


class SpecialtyShowDJ(Base):
    """One DJ member of a Specialty Music Show: a Spinitron persona."""

    __tablename__ = "specialty_show_djs"

    id = Column(Integer, primary_key=True, index=True)
    specialty_show_id = Column(Integer, ForeignKey("specialty_shows.id"), nullable=False)
    persona_id = Column(Integer, nullable=False, index=True)

    specialty_show = relationship("SpecialtyShow", back_populates="djs")

    @property
    def name(self) -> str:
        """The persona's current name (see `credit`)."""
        return persona_name(object_session(self), self.persona_id) or (
            f"Persona #{self.persona_id}"
        )
