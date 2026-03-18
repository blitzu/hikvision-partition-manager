"""NVR CRUD API routes.

Endpoints:
  POST /api/locations/{location_id}/nvrs  — create NVR for a location
  GET  /api/locations/{location_id}/nvrs  — list NVRs for a location
  GET  /api/nvrs/{nvr_id}/test            — test NVR connectivity via ISAPI

Security (NVR-06): body.password is encrypted before any DB call.
The plaintext value is used ONLY as an argument to encrypt_password() and is
never stored, logged, or serialized. NVRRead has no password field at all.
"""
import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import decrypt_password, encrypt_password
from app.core.database import get_db
from app.core.schemas import APIResponse
from app.isapi.client import ISAPIClient
from app.locations.models import Location
from app.nvrs.models import NVRDevice
from app.nvrs.schemas import NVRCreate, NVRRead, NVRUpdate

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


@router.patch(
    "/nvrs/{nvr_id}",
    response_model=APIResponse[NVRRead],
)
async def update_nvr(
    nvr_id: uuid.UUID,
    body: NVRUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> APIResponse[NVRRead]:
    """Update NVR device fields. Only provided fields are changed.
    If password is provided, it is encrypted before DB write (NVR-06).
    """
    nvr = await db.get(NVRDevice, nvr_id)
    if nvr is None:
        return APIResponse(success=False, error="NVR not found")

    if body.name is not None:
        nvr.name = body.name
    if body.ip_address is not None:
        nvr.ip_address = body.ip_address
    if body.port is not None:
        nvr.port = body.port
    if body.username is not None:
        nvr.username = body.username
    if body.password is not None:
        nvr.password_encrypted = encrypt_password(body.password)

    await db.commit()
    return APIResponse(success=True, data=NVRRead.model_validate(nvr))


@router.get(
    "/nvrs/{nvr_id}/test",
    response_model=APIResponse[dict],
)
async def test_connectivity(
    nvr_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> APIResponse[dict]:
    """Test NVR connectivity via ISAPI System/deviceInfo.

    Always returns HTTP 200.  success=true means NVR responded;
    success=false means NVR not found or ISAPI unreachable (NVR-03).
    NVR-05: last_seen_at and status updated on every ISAPI contact.
    NVR-06: password never logged or included in error messages.
    """
    nvr = await db.get(NVRDevice, nvr_id)
    if nvr is None:
        return APIResponse(success=False, error="NVR not found")

    # NVR-06: decrypt only within this scope; never log or format into strings
    password = decrypt_password(nvr.password_encrypted)
    isapi_client = ISAPIClient(nvr.ip_address, nvr.port, nvr.username, password)

    try:
        device_info = await isapi_client.get_device_info()
        # NVR-05: update last_seen_at and status after every successful contact
        nvr.last_seen_at = datetime.now(UTC)
        nvr.status = "online"
        await db.commit()
        return APIResponse(success=True, data=device_info)
    except Exception as exc:
        # NVR-06: log only exception class name — never format password or URL with auth
        nvr.status = "offline"
        await db.commit()
        return APIResponse(
            success=False,
            error=f"NVR unreachable: {type(exc).__name__}",
        )
