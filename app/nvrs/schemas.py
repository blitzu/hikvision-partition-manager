"""Pydantic schemas for NVR domain.

Security contract (NVR-06):
- NVRCreate accepts plaintext password on input only.
- NVRRead has NO password or password_encrypted field — exclusion is structural.
  The field does not exist on this schema, making leakage impossible at the
  serialization layer regardless of what is stored in the ORM model.
"""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NVRCreate(BaseModel):
    """Input schema for creating an NVR device.

    The 'password' field accepts plaintext. It is encrypted BEFORE any DB
    call and is NEVER stored in plaintext or returned in any response.
    """

    name: str
    ip_address: str
    port: int = 8000
    username: str
    password: str  # plaintext on create only — NEVER returned


class NVRUpdate(BaseModel):
    """Input schema for updating an NVR device. All fields optional."""

    name: str | None = None
    ip_address: str | None = None
    port: int | None = None
    username: str | None = None
    password: str | None = None  # plaintext — encrypted before DB write if provided


class NVRRead(BaseModel):
    """Output schema for an NVR device.

    NO password field — not 'password', not 'password_encrypted'.
    Exclusion is structural: the field does not exist on this schema.
    """

    id: uuid.UUID
    name: str
    ip_address: str
    port: int
    username: str
    location_id: uuid.UUID
    status: str
    last_seen_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
