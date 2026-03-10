"""Pydantic schemas for Location domain."""
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, field_validator


class LocationCreate(BaseModel):
    """Input schema for creating a location."""

    name: str
    timezone: str

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        try:
            ZoneInfo(v)
        except ZoneInfoNotFoundError:
            raise ValueError(f"Unknown timezone: {v!r}")
        return v


class LocationRead(BaseModel):
    """Output schema for a location. No sensitive fields."""

    id: uuid.UUID
    name: str
    timezone: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
