"""Shared Pydantic types for consistent API serialization."""

from datetime import datetime, timezone
from typing import Annotated

from pydantic import BeforeValidator


def _ensure_utc(v: object) -> object:
    if isinstance(v, datetime) and v.tzinfo is None:
        return v.replace(tzinfo=timezone.utc)
    return v


UtcDatetime = Annotated[datetime, BeforeValidator(_ensure_utc)]
