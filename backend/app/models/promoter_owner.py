"""PromoterOwner model — maps promoters to promotions staff owners."""

from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class PromoterOwner(Base):
    """Associates a promoter with one or more promotions staff members."""

    __tablename__ = "promoter_owners"

    id = Column(Integer, primary_key=True, index=True)
    promoter_id = Column(Integer, ForeignKey("promoters.id"), nullable=False)
    staff_id = Column(Integer, ForeignKey("staff.id"), nullable=False)

    promoter = relationship("Promoter", back_populates="owners")
    staff = relationship("Staff")

    @property
    def promotions_staff_email(self) -> str | None:
        return self.staff.email if self.staff else None
