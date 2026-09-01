"""Pydantic schemas for Promoter API."""

from pydantic import BaseModel, Field, ConfigDict


class PromoterContactCreate(BaseModel):
    name: str | None = None
    title: str | None = None
    email: str | None = None
    phone: str | None = None


class PromoterContactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str | None = None
    title: str | None = None
    email: str | None = None
    phone: str | None = None


class PromoterCreate(BaseModel):
    """Schema for creating a new promoter."""

    name: str = Field(
        ..., min_length=1, max_length=200, description="Promoter name (must be unique)"
    )
    pass_call_instructions: str | None = None
    requires_phone_number: bool = False
    requires_email_address: bool = False
    staff_guest_requires_name: bool = False
    owner_emails: list[str] = Field(default_factory=list)
    contacts: list[PromoterContactCreate] = Field(default_factory=list)


class PromoterUpdate(BaseModel):
    """Schema for updating an existing promoter."""

    name: str | None = Field(None, min_length=1, max_length=200)
    pass_call_instructions: str | None = None
    requires_phone_number: bool | None = None
    requires_email_address: bool | None = None
    staff_guest_requires_name: bool | None = None
    owner_emails: list[str] | None = None
    contacts: list[PromoterContactCreate] | None = None


class PromoterResponse(BaseModel):
    """Schema for promoter response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    pass_call_instructions: str | None = None
    requires_phone_number: bool = False
    requires_email_address: bool = False
    staff_guest_requires_name: bool = False
    deleted: bool = False
    owner_emails: list[str] = Field(default_factory=list)
    contacts: list[PromoterContactResponse] = Field(default_factory=list)

    @classmethod
    def from_orm_promoter(cls, promoter):
        return cls(
            id=promoter.id,
            name=promoter.name,
            pass_call_instructions=promoter.pass_call_instructions,
            requires_phone_number=promoter.requires_phone_number,
            requires_email_address=promoter.requires_email_address,
            staff_guest_requires_name=promoter.staff_guest_requires_name,
            deleted=promoter.deleted,
            owner_emails=[o.promotions_staff_email for o in promoter.owners],
            contacts=[PromoterContactResponse.model_validate(c) for c in promoter.contacts],
        )
