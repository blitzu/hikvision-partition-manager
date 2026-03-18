"""Camera routes.

Endpoints:
  GET /api/nvrs/{nvr_id}/cameras/sync  — sync cameras from NVR via ISAPI

NVR-04: Upsert ensures idempotent sync — double-sync creates no duplicates.
NVR-05: NVR last_seen_at and status updated after successful ISAPI contact.
NVR-06: password decrypted only within function scope, never logged.
"""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cameras.models import Camera
from app.cameras.schemas import CameraRead
from app.cameras.service import sync_cameras_from_nvr
from app.core.database import get_db
from app.core.schemas import APIResponse

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
    result = await sync_cameras_from_nvr(nvr_id, db)
    if not result["success"]:
        return APIResponse(success=False, error=result["error"])

    cameras_result = await db.execute(
        select(Camera).where(Camera.nvr_id == nvr_id)
    )
    cameras = cameras_result.scalars().all()

    return APIResponse(
        success=True,
        data=[CameraRead.model_validate(cam) for cam in cameras],
    )
