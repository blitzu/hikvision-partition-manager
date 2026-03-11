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
from sqlalchemy import select

from app.cameras.routes import router as cameras_router
from app.core.database import async_session_factory, engine
from app.jobs.auto_rearm import schedule_rearm
from app.jobs.scheduler import shutdown_scheduler, start_scheduler
from app.locations.routes import router as locations_router
from app.nvrs.routes import router as nvrs_router
from app.partitions.models import Partition, PartitionState
from app.partitions.routes import router as partitions_router, dashboard_router

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
    await start_scheduler()
    await _reconcile_missed_rearm_jobs()
    yield
    await shutdown_scheduler()
    await engine.dispose()


app = FastAPI(
    title="Hikvision Partition Manager",
    lifespan=lifespan,
)

app.include_router(locations_router)
app.include_router(nvrs_router)
app.include_router(cameras_router)
app.include_router(partitions_router)
app.include_router(dashboard_router)
