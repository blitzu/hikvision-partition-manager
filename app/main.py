"""FastAPI application entry point.

Lifespan runs Alembic migrations on startup via asyncio.to_thread
(required to avoid threading.local issues with Alembic's sync context).
"""
import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from alembic import command
from alembic.config import Config
from fastapi import FastAPI

from app.cameras.routes import router as cameras_router
from app.core.database import engine
from app.locations.routes import router as locations_router
from app.nvrs.routes import router as nvrs_router
from app.partitions.routes import router as partitions_router, dashboard_router


def _run_migrations() -> None:
    """Run alembic upgrade head. Executes synchronously in a thread pool."""
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: run migrations on startup, dispose engine on shutdown."""
    await asyncio.to_thread(_run_migrations)
    yield
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
