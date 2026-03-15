"""Shared AsyncScheduler instance.

Uses SQLAlchemyDataStore backed by the existing app engine so jobs survive
process restarts. The module-level `scheduler` instance is imported by other
job modules to schedule/cancel jobs.

Lifecycle: use `async with scheduler:` in the FastAPI lifespan, then call
`await scheduler.start_in_background()` inside that block. APScheduler 4.x
requires the async context manager to be active for the full lifespan.
"""
import logging

from apscheduler import AsyncScheduler
from apscheduler.datastores.sqlalchemy import SQLAlchemyDataStore

from app.core.database import engine

logger = logging.getLogger(__name__)

# Module-level scheduler instance backed by the existing PostgreSQL engine.
# The lifespan in app/main.py owns the `async with scheduler:` context.
data_store = SQLAlchemyDataStore(engine)
scheduler = AsyncScheduler(data_store=data_store)
