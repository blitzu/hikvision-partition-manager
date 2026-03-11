"""Background monitor jobs: stuck-disarmed partition alerting and NVR health checks.

Provides:
- stuck_disarmed_monitor(): queries overdue disarmed partitions and fires webhooks
- nvr_health_check(): pings all NVRs, updates status, fires offline/online webhooks

Both functions open their own DB session via async_session_factory.
Webhooks are delivered non-blocking via asyncio.create_task(deliver_webhook(...)).
"""
import asyncio
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.crypto import decrypt_password
from app.core.database import async_session_factory
from app.isapi.client import ISAPIClient
from app.jobs.auto_rearm import deliver_webhook
from app.locations.models import Location
from app.nvrs.models import NVRDevice
from app.partitions.models import Partition, PartitionState

logger = logging.getLogger(__name__)

# Module-level state for NVR transition tracking
_nvr_prev_status: dict[uuid.UUID, str] = {}
_nvr_last_offline_alert: dict[uuid.UUID, datetime] = {}

OFFLINE_ALERT_COOLDOWN_SECONDS = 300  # 5 minutes


async def stuck_disarmed_monitor() -> None:
    """Query all overdue disarmed partitions and fire partition_stuck_disarmed webhooks.

    Runs every 5 minutes. Fires one webhook per overdue partition per cycle.
    Continues until the partition is re-armed.
    """
    async with async_session_factory() as db:
        stmt = (
            select(Partition, PartitionState)
            .join(PartitionState, PartitionState.partition_id == Partition.id)
            .where(
                PartitionState.state == "disarmed",
                Partition.alert_if_disarmed_minutes.is_not(None),
                Partition.deleted_at.is_(None),
            )
        )
        result = await db.execute(stmt)
        rows = result.all()

    now = datetime.now(timezone.utc)

    for partition, state in rows:
        if state.last_changed_at is None:
            continue

        # Ensure last_changed_at is timezone-aware for comparison
        last_changed = state.last_changed_at
        if last_changed.tzinfo is None:
            last_changed = last_changed.replace(tzinfo=timezone.utc)

        minutes_elapsed = (now - last_changed).total_seconds() / 60

        if minutes_elapsed >= partition.alert_if_disarmed_minutes:
            payload = {
                "type": "partition_stuck_disarmed",
                "partition_id": str(partition.id),
                "partition_name": partition.name,
                "disarmed_by": state.last_changed_by,
                "disarmed_at": last_changed.isoformat(),
                "minutes_elapsed": minutes_elapsed,
                "scheduled_rearm_at": (
                    state.scheduled_rearm_at.isoformat()
                    if state.scheduled_rearm_at is not None
                    else None
                ),
            }
            asyncio.create_task(deliver_webhook(payload))
            logger.info(
                "Stuck-disarmed alert fired for partition %s (%.1f min elapsed, threshold %d min).",
                partition.id,
                minutes_elapsed,
                partition.alert_if_disarmed_minutes,
            )


async def nvr_health_check() -> None:
    """Ping all NVRs via ISAPI, update status, and fire transition webhooks.

    Runs every 60 seconds. Tracks status transitions using module-level dicts.
    - offline transition: fires nvr_offline webhook (with 5-min cooldown)
    - online transition (recovery): fires nvr_online webhook
    Commits all NVR status updates in a single bulk commit.
    """
    async with async_session_factory() as db:
        stmt = (
            select(NVRDevice, Location.name)
            .join(Location, NVRDevice.location_id == Location.id)
        )
        result = await db.execute(stmt)
        rows = result.all()

        now = datetime.now(timezone.utc)

        for nvr, location_name in rows:
            prev_status = _nvr_prev_status.get(nvr.id, nvr.status)

            try:
                password = decrypt_password(nvr.password_encrypted)
                client = ISAPIClient(
                    host=nvr.ip_address,
                    port=nvr.port,
                    username=nvr.username,
                    password=password,
                )
                await client.get_device_info()
                new_status = "online"
                nvr.status = new_status
                nvr.last_seen_at = now
            except Exception as exc:
                logger.warning("NVR %s (%s) health check failed: %s", nvr.id, nvr.name, exc)
                new_status = "offline"
                nvr.status = new_status
                # last_seen_at is NOT updated on failure

            # Detect offline transition
            if prev_status != "offline" and new_status == "offline":
                # Check cooldown before firing
                last_alert = _nvr_last_offline_alert.get(nvr.id)
                if last_alert is None or (now - last_alert).total_seconds() >= OFFLINE_ALERT_COOLDOWN_SECONDS:
                    payload = {
                        "type": "nvr_offline",
                        "nvr_id": str(nvr.id),
                        "nvr_name": nvr.name,
                        "location_name": location_name,
                    }
                    asyncio.create_task(deliver_webhook(payload))
                    _nvr_last_offline_alert[nvr.id] = now
                    logger.warning("NVR offline alert fired for %s (%s).", nvr.id, nvr.name)
                else:
                    logger.debug(
                        "NVR offline alert suppressed for %s (cooldown active).", nvr.id
                    )

            # Also fire offline alert if already offline but cooldown expired
            # (i.e., prev == 'offline' AND new == 'offline' AND cooldown expired)
            elif prev_status == "offline" and new_status == "offline":
                last_alert = _nvr_last_offline_alert.get(nvr.id)
                if last_alert is not None and (now - last_alert).total_seconds() >= OFFLINE_ALERT_COOLDOWN_SECONDS:
                    payload = {
                        "type": "nvr_offline",
                        "nvr_id": str(nvr.id),
                        "nvr_name": nvr.name,
                        "location_name": location_name,
                    }
                    asyncio.create_task(deliver_webhook(payload))
                    _nvr_last_offline_alert[nvr.id] = now
                    logger.warning(
                        "NVR offline re-alert fired for %s (cooldown expired).", nvr.id
                    )

            # Detect online recovery transition
            elif prev_status == "offline" and new_status == "online":
                payload = {
                    "type": "nvr_online",
                    "nvr_id": str(nvr.id),
                    "nvr_name": nvr.name,
                    "location_name": location_name,
                }
                asyncio.create_task(deliver_webhook(payload))
                logger.info("NVR online recovery alert fired for %s (%s).", nvr.id, nvr.name)

            _nvr_prev_status[nvr.id] = new_status

        await db.commit()
