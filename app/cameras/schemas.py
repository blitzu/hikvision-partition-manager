"""Pydantic schemas for Camera API responses."""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CameraRead(BaseModel):
    """Schema for reading camera data in API responses."""

    id: uuid.UUID
    nvr_id: uuid.UUID
    channel_no: int
    name: str | None
    enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
