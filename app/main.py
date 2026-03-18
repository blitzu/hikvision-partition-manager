"""FastAPI application entry point.

Lifespan runs Alembic migrations on startup via asyncio.to_thread
(required to avoid threading.local issues with Alembic's sync context).
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from apscheduler import ConflictPolicy
from apscheduler.triggers.interval import IntervalTrigger

from app.cameras.routes import router as cameras_router
from app.core.config import settings
from app.core.database import async_session_factory, engine
from app.core.inflight import wait_drain
from app.core.logging import memory_handler, setup_logging
from app.jobs.auto_rearm import schedule_rearm
from app.jobs.monitors import nvr_health_check, stuck_disarmed_monitor
from app.jobs.scheduler import scheduler
from app.locations.routes import router as locations_router
from app.middleware.logging import RequestLoggingMiddleware
from app.nvrs.routes import router as nvrs_router
from app.partitions.models import Partition, PartitionState
from app.partitions.routes import router as partitions_router, dashboard_router
from app.ui.routes import ui_router

setup_logging(settings.LOG_LEVEL)

logger = logging.getLogger(__name__)


def _run_migrations() -> None:
    """Run alembic upgrade head. Executes synchronously in a thread pool."""
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")


async def _reconcile_missed_rearm_jobs() -> None:
    """Re-register any auto-rearm jobs that are missing from the scheduler.

    Queries all PartitionState rows that are disarmed with a scheduled_rearm_at,
    then re-schedules any that don't already have a job in APScheduler. If the
    scheduled time is already past, APScheduler fires the job immediately (default
    misfire behavior — partition gets rearmed promptly even if late).
    """
    from app.jobs.scheduler import scheduler  # avoid circular import at module-level

    async with async_session_factory() as db:
        stmt = (
            select(PartitionState)
            .where(
                PartitionState.state == "disarmed",
                PartitionState.scheduled_rearm_at.is_not(None),
            )
        )
        result = await db.execute(stmt)
        states = result.scalars().all()

    for state in states:
        job_id = f"rearm:{state.partition_id}"
        try:
            await scheduler.get_schedule(job_id)
            logger.debug("Auto-rearm schedule already exists for partition %s.", state.partition_id)
        except Exception:
            # Schedule not found — re-register it
            logger.info(
                "Reconciling missed auto-rearm for partition %s at %s.",
                state.partition_id,
                state.scheduled_rearm_at,
            )
            await schedule_rearm(state.partition_id, state.scheduled_rearm_at)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: run migrations on startup, dispose engine on shutdown."""
    await asyncio.to_thread(_run_migrations)
    # Re-attach memory_handler after uvicorn resets the logging config at startup
    root_logger = logging.getLogger()
    if memory_handler not in root_logger.handlers:
        root_logger.addHandler(memory_handler)
    # Ensure root level allows INFO so sync logs are captured
    if root_logger.level > logging.INFO:
        root_logger.setLevel(logging.INFO)
    logger.info("Application started — log viewer available at /admin/logs")
    async with scheduler:
        await scheduler.start_in_background()
        await _reconcile_missed_rearm_jobs()
        # Register stuck-disarmed monitor: interval driven by POLL_INTERVAL_SECONDS config
        await scheduler.add_schedule(
            stuck_disarmed_monitor,
            IntervalTrigger(seconds=settings.POLL_INTERVAL_SECONDS),
            id="stuck_disarmed_monitor",
            conflict_policy=ConflictPolicy.replace,
        )
        # Register NVR health check: every 60 seconds
        await scheduler.add_schedule(
            nvr_health_check,
            IntervalTrigger(seconds=60),
            id="nvr_health_check",
            conflict_policy=ConflictPolicy.replace,
        )
        yield
    remaining = await wait_drain(timeout=30.0)
    if remaining > 0:
        logger.warning(
            "Shutdown forced with active ISAPI calls",
            extra={"event": "shutdown_forced", "active_isapi_calls": remaining, "component": "http"},
        )
    await engine.dispose()


app = FastAPI(
    title="Hikvision Partition Manager",
    lifespan=lifespan,
)

app.add_middleware(RequestLoggingMiddleware)
app.include_router(locations_router)
app.include_router(nvrs_router)
app.include_router(cameras_router)
app.include_router(partitions_router)
app.include_router(dashboard_router)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(ui_router)
