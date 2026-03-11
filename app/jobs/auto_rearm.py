"""Auto-rearm job: schedule, cancel, and execute partition auto-rearm.

Provides:
- schedule_rearm(partition_id, run_at): add a one-shot DateTrigger schedule
- cancel_rearm(partition_id): remove the pending schedule (no-op if missing)
- auto_rearm_job(partition_id_str): the actual job function, opens its own DB session
- deliver_webhook(payload): async POST with 3 retries; non-blocking via create_task
"""
import asyncio
import logging
import uuid
from datetime import datetime

import httpx
from apscheduler import ConflictPolicy, ScheduleLookupError
from apscheduler.triggers.date import DateTrigger

from app.core.config import settings
from app.core.database import async_session_factory
from app.jobs.scheduler import scheduler

logger = logging.getLogger(__name__)

# Retry delays (seconds) between attempts — first attempt has no delay
_RETRY_DELAYS = [1, 5, 15]


async def deliver_webhook(payload: dict) -> None:
    """POST payload to ALERT_WEBHOOK_URL with 5s timeout.

    Retries up to 3 times with delays [1, 5, 15]s between attempts.
    Logs failures and returns silently — never raises.
    """
    url = settings.ALERT_WEBHOOK_URL
    if not url:
        logger.debug("ALERT_WEBHOOK_URL not configured — skipping webhook delivery.")
        return

    last_error: Exception | None = None
    for attempt in range(4):  # attempt 0 = first try; attempts 1-3 = retries
        if attempt > 0:
            delay = _RETRY_DELAYS[attempt - 1]
            logger.warning(
                "Webhook delivery attempt %d failed, retrying in %ss: %s",
                attempt,
                delay,
                last_error,
            )
            await asyncio.sleep(delay)

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
            logger.info("Webhook delivered successfully on attempt %d.", attempt + 1)
            return
        except Exception as exc:
            last_error = exc

    logger.error(
        "Webhook delivery failed after %d attempts. Last error: %s",
        4,
        last_error,
    )


async def schedule_rearm(partition_id: uuid.UUID, run_at: datetime) -> None:
    """Add (or replace) a DateTrigger schedule to auto-rearm the partition at run_at."""
    await scheduler.add_schedule(
        auto_rearm_job,
        DateTrigger(run_time=run_at),
        id=f"rearm:{partition_id}",
        kwargs={"partition_id_str": str(partition_id)},
        conflict_policy=ConflictPolicy.replace,
    )
    logger.info("Scheduled auto-rearm for partition %s at %s.", partition_id, run_at)


async def cancel_rearm(partition_id: uuid.UUID) -> None:
    """Remove the pending auto-rearm schedule. No-op if no schedule exists."""
    try:
        await scheduler.remove_schedule(f"rearm:{partition_id}")
        logger.info("Cancelled auto-rearm schedule for partition %s.", partition_id)
    except ScheduleLookupError:
        # No schedule found — normal if arm was called without a prior disarm
        pass


async def auto_rearm_job(partition_id_str: str) -> None:
    """Execute auto-rearm: open own DB session, arm partition, fire webhook.

    Uses deferred import of arm_partition to avoid circular imports at module level.
    """
    # Deferred import to break the circular import chain:
    # auto_rearm.py (module-level) -> service.py -> auto_rearm.py
    from app.partitions.service import arm_partition  # noqa: PLC0415

    partition_id = uuid.UUID(partition_id_str)
    partition_name: str | None = None

    try:
        async with async_session_factory() as db:
            arm_result = await arm_partition(partition_id, "system:auto_rearm", db)
            # Fetch partition name for the webhook payload
            from app.partitions.models import Partition  # noqa: PLC0415
            partition = await db.get(Partition, partition_id)
            if partition:
                partition_name = partition.name

        logger.info(
            "Auto-rearm completed for partition %s (%s restored, %s kept disarmed).",
            partition_id,
            arm_result.cameras_restored,
            arm_result.cameras_kept_disarmed,
        )
    except Exception as exc:
        logger.error("Auto-rearm job failed for partition %s: %s", partition_id, exc)
        return

    # Fire webhook non-blocking — job is considered complete regardless of webhook outcome
    payload = {
        "type": "auto_rearmed",
        "partition_id": str(partition_id),
        "partition_name": partition_name or "",
    }
    asyncio.create_task(deliver_webhook(payload))
