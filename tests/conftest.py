"""Test fixtures: engine, db_session, and AsyncClient.

Using function-scoped engine for schema tests to avoid asyncio event loop
cross-contamination with asyncpg connection pools. The session-scoped
approach requires pytest-asyncio 0.24+ with explicit loop_scope; we use
function-scoped here for compatibility with pytest-asyncio 0.23.x.
"""
import os
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.database import Base, get_db
from app.main import app

# Import all models to ensure Base.metadata is fully populated before create_all.
# This mirrors the import pattern used in alembic/env.py.
from app.locations.models import Location  # noqa: F401
from app.nvrs.models import NVRDevice  # noqa: F401
from app.cameras.models import Camera  # noqa: F401
from app.partitions.models import (  # noqa: F401
    Partition,
    PartitionCamera,
    PartitionState,
    CameraDetectionSnapshot,
    CameraDisarmRefcount,
    PartitionAuditLog,
)

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://appuser:apppassword@localhost:5432/test_partitions",
)


@pytest.fixture(autouse=True)
def mock_scheduler_calls(request):
    """Auto-mock schedule_rearm and cancel_rearm in partition service for all tests.

    This prevents calls to the APScheduler instance (which requires a running DB
    connection) during integration/API tests. Tests in test_jobs_auto_rearm.py
    already mock the scheduler module directly and are excluded here.
    """
    if "test_jobs_auto_rearm" in request.fspath.basename:
        # Those tests mock the scheduler themselves
        yield
        return

    with patch("app.partitions.service.schedule_rearm", new_callable=AsyncMock) as mock_sched, \
         patch("app.partitions.service.cancel_rearm", new_callable=AsyncMock) as mock_cancel:
        yield {"schedule_rearm": mock_sched, "cancel_rearm": mock_cancel}


@pytest_asyncio.fixture(scope="function")
async def engine():
    """Function-scoped async engine. Creates all tables before test, drops after.

    Schema tests use this directly. CRUD tests use db_session which builds on this.
    Function scope avoids asyncio event loop / asyncpg connection pool mismatch
    when using pytest-asyncio 0.23.x asyncio_mode=auto.
    """
    eng = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(engine):
    """Function-scoped session using connection-level transaction for rollback isolation."""
    async with engine.connect() as conn:
        await conn.begin()
        session = AsyncSession(bind=conn, expire_on_commit=False)
        yield session
        await session.close()
        await conn.rollback()


@pytest_asyncio.fixture(scope="function")
async def client(db_session):
    """AsyncClient with get_db dependency overridden to use the test session."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()
