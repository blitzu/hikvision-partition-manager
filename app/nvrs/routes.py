"""NVR CRUD API routes.

Endpoints:
  POST /api/locations/{location_id}/nvrs  — create NVR for a location
  GET  /api/locations/{location_id}/nvrs  — list NVRs for a location

Security (NVR-06): body.password is encrypted before any DB call.
The plaintext value is used ONLY as an argument to encrypt_password() and is
never stored, logged, or serialized. NVRRead has no password field at all.
"""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import encrypt_password
from app.core.database import get_db
from app.core.schemas import APIResponse
from app.locations.models import Location
from app.nvrs.models import NVRDevice
from app.nvrs.schemas import NVRCreate, NVRRead

router = APIRouter(prefix="/api", tags=["nvrs"])


@router.post(
    "/locations/{location_id}/nvrs",
    response_model=APIResponse[NVRRead],
)
async def create_nvr(
    location_id: uuid.UUID,
    body: NVRCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> APIResponse[NVRRead]:
    """Create an NVR device linked to a location.

    Password is encrypted with Fernet before any database write.
    The plaintext value never leaves this function.
    """
    location = await db.get(Location, location_id)
    if location is None:
        return APIResponse(success=False, error="Location not found")

    # Encrypt BEFORE any DB call — NVR-06 compliance
    encrypted = encrypt_password(body.password)

    nvr = NVRDevice(
        location_id=location_id,
        name=body.name,
        ip_address=body.ip_address,
        port=body.port,
        username=body.username,
        password_encrypted=encrypted,
    )
    db.add(nvr)
    await db.commit()

    return APIResponse(success=True, data=NVRRead.model_validate(nvr))


@router.get(
    "/locations/{location_id}/nvrs",
    response_model=APIResponse[list[NVRRead]],
)
async def list_nvrs(
    location_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> APIResponse[list[NVRRead]]:
    """List all NVR devices for a location."""
    location = await db.get(Location, location_id)
    if location is None:
        return APIResponse(success=False, error="Location not found")

    result = await db.execute(
        select(NVRDevice).where(NVRDevice.location_id == location_id)
    )
    nvrs = result.scalars().all()

    return APIResponse(
        success=True,
        data=[NVRRead.model_validate(nvr) for nvr in nvrs],
    )
