"""Shared AsyncScheduler instance and lifespan helpers.

Uses SQLAlchemyDataStore backed by the existing app engine so jobs survive
process restarts. The module-level `scheduler` instance is imported by other
job modules to schedule/cancel jobs.
"""
import logging

from apscheduler import AsyncScheduler
from apscheduler.datastores.sqlalchemy import SQLAlchemyDataStore

from app.core.database import engine

logger = logging.getLogger(__name__)

# Module-level scheduler instance backed by the existing PostgreSQL engine.
# Start/stop is managed via lifespan helpers called from app/main.py.
data_store = SQLAlchemyDataStore(engine)
scheduler = AsyncScheduler(data_store=data_store)


async def start_scheduler() -> None:
    """Start the APScheduler AsyncScheduler in the background."""
    logger.info("Starting APScheduler...")
    await scheduler.start_in_background()
    logger.info("APScheduler started.")


async def shutdown_scheduler() -> None:
    """Gracefully stop the APScheduler."""
    logger.info("Shutting down APScheduler...")
    await scheduler.stop()
    logger.info("APScheduler stopped.")
