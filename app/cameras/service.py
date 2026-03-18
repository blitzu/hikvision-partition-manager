"""Camera service — core sync logic shared by API route and UI route."""
import logging
import uuid
from datetime import UTC, datetime

import httpx
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.cameras.models import Camera
from app.core.crypto import decrypt_password
from app.isapi.client import ISAPIClient
from app.nvrs.models import NVRDevice

logger = logging.getLogger("cameras.sync")


async def sync_cameras_from_nvr(
    nvr_id: uuid.UUID, db: AsyncSession
) -> dict:
    """Sync cameras from NVR ISAPI into the database.

    Returns {"success": bool, "count": int, "error": str | None}.
    Never raises — all errors are captured in the return value.
    """
    nvr = await db.get(NVRDevice, nvr_id)
    if nvr is None:
        logger.warning("Sync failed — NVR not found", extra={"nvr_id": str(nvr_id)})
        return {"success": False, "count": 0, "error": "NVR not found"}

    logger.info(
        "Starting camera sync",
        extra={"nvr_id": str(nvr_id), "nvr_name": nvr.name, "host": f"{nvr.ip_address}:{nvr.port}"},
    )

    password = decrypt_password(nvr.password_encrypted)
    isapi_client = ISAPIClient(nvr.ip_address, nvr.port, nvr.username, password)

    try:
        channels = await isapi_client.get_camera_channels()
    except httpx.HTTPStatusError as exc:
        logger.error(
            "Camera sync failed — HTTP error from NVR",
            extra={
                "nvr_id": str(nvr_id),
                "nvr_name": nvr.name,
                "status_code": exc.response.status_code,
                "url": str(exc.request.url),
                "response_body": exc.response.text[:500],
            },
        )
        nvr.status = "offline"
        await db.commit()
        return {"success": False, "count": 0, "error": f"HTTP {exc.response.status_code} from NVR"}
    except httpx.TimeoutException:
        logger.error(
            "Camera sync failed — timeout connecting to NVR",
            extra={"nvr_id": str(nvr_id), "nvr_name": nvr.name, "host": f"{nvr.ip_address}:{nvr.port}"},
        )
        nvr.status = "offline"
        await db.commit()
        return {"success": False, "count": 0, "error": "Connection timed out"}
    except Exception as exc:
        logger.error(
            "Camera sync failed — unexpected error",
            extra={"nvr_id": str(nvr_id), "nvr_name": nvr.name, "error_type": type(exc).__name__, "error": str(exc)},
        )
        nvr.status = "offline"
        await db.commit()
        return {"success": False, "count": 0, "error": f"ISAPI error: {type(exc).__name__}"}

    logger.info(
        "ISAPI returned channels",
        extra={"nvr_id": str(nvr_id), "nvr_name": nvr.name, "channel_count": len(channels), "channels": channels},
    )

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

    nvr.last_seen_at = datetime.now(UTC)
    nvr.status = "online"
    await db.commit()

    logger.info(
        "Camera sync complete",
        extra={"nvr_id": str(nvr_id), "nvr_name": nvr.name, "synced": len(channels)},
    )

    return {"success": True, "count": len(channels), "error": None}
