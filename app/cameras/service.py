"""Camera service — core sync logic shared by API route and UI route."""
import uuid
from datetime import UTC, datetime

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

import httpx

from app.cameras.models import Camera
from app.core.crypto import decrypt_password
from app.isapi.client import ISAPIClient
from app.nvrs.models import NVRDevice


async def sync_cameras_from_nvr(
    nvr_id: uuid.UUID, db: AsyncSession
) -> dict:
    """Sync cameras from NVR ISAPI into the database.

    Returns {"success": bool, "count": int, "error": str | None}.
    Never raises — all errors are captured in the return value.
    """
    nvr = await db.get(NVRDevice, nvr_id)
    if nvr is None:
        return {"success": False, "count": 0, "error": "NVR not found"}

    password = decrypt_password(nvr.password_encrypted)
    isapi_client = ISAPIClient(nvr.ip_address, nvr.port, nvr.username, password)

    try:
        channels = await isapi_client.get_camera_channels()
    except httpx.HTTPStatusError as exc:
        nvr.status = "offline"
        await db.commit()
        return {"success": False, "count": 0, "error": f"HTTP {exc.response.status_code} from NVR"}
    except Exception as exc:
        nvr.status = "offline"
        await db.commit()
        return {"success": False, "count": 0, "error": f"ISAPI error: {type(exc).__name__}"}

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

    return {"success": True, "count": len(channels), "error": None}
