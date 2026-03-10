"""Camera routes.

Endpoints:
  GET /api/nvrs/{nvr_id}/cameras/sync  — sync cameras from NVR via ISAPI

NVR-04: Upsert ensures idempotent sync — double-sync creates no duplicates.
NVR-05: NVR last_seen_at and status updated after successful ISAPI contact.
NVR-06: password decrypted only within function scope, never logged.
"""
import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.cameras.models import Camera
from app.cameras.schemas import CameraRead
from app.core.crypto import decrypt_password
from app.core.database import get_db
from app.core.schemas import APIResponse
from app.isapi.client import ISAPIClient
from app.nvrs.models import NVRDevice

router = APIRouter(prefix="/api/nvrs", tags=["cameras"])


@router.get(
    "/{nvr_id}/cameras/sync",
    response_model=APIResponse[list[CameraRead]],
)
async def sync_cameras(
    nvr_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> APIResponse[list[CameraRead]]:
    """Sync cameras from NVR ISAPI into the database.

    Uses PostgreSQL ON CONFLICT DO UPDATE for idempotent upserts (NVR-04).
    Updates NVR last_seen_at and status on every successful ISAPI contact (NVR-05).
    Always returns HTTP 200; success=false envelope on any error.
    """
    nvr = await db.get(NVRDevice, nvr_id)
    if nvr is None:
        return APIResponse(success=False, error="NVR not found")

    # NVR-06: decrypt only within this scope
    password = decrypt_password(nvr.password_encrypted)
    isapi_client = ISAPIClient(nvr.ip_address, nvr.port, nvr.username, password)

    try:
        channels = await isapi_client.get_camera_channels()
    except Exception as exc:
        # NVR-06: log only class name — never format password or URL with auth
        nvr.status = "offline"
        await db.commit()
        return APIResponse(
            success=False,
            error=f"ISAPI error: {type(exc).__name__}",
        )

    # NVR-04: Upsert each channel — ON CONFLICT DO UPDATE prevents duplicates
    for ch in channels:
        stmt = pg_insert(Camera).values(
            nvr_id=nvr.id,
            channel_no=ch["channel_no"],
            name=ch.get("name"),
            enabled=True,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["nvr_id", "channel_no"],
            set_={
                "name": stmt.excluded.name,
                "updated_at": func.now(),
            },
        )
        await db.execute(stmt)

    await db.commit()

    # NVR-05: update last_seen_at and status after successful sync
    nvr.last_seen_at = datetime.now(UTC)
    nvr.status = "online"
    await db.commit()

    # Query and return all cameras for this NVR
    result = await db.execute(
        select(Camera).where(Camera.nvr_id == nvr_id)
    )
    cameras = result.scalars().all()

    return APIResponse(
        success=True,
        data=[CameraRead.model_validate(cam) for cam in cameras],
    )
