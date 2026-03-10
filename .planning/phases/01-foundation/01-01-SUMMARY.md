---
phase: 01-foundation
plan: "01"
subsystem: database
tags: [fastapi, sqlalchemy, alembic, postgresql, asyncpg, pydantic, cryptography, fernet, pytest-asyncio]

# Dependency graph
requires: []
provides:
  - All 9 PostgreSQL tables created via single Alembic migration (locations, nvr_devices, cameras, partitions, partition_cameras, partition_state, camera_detection_snapshot, camera_disarm_refcount, partition_audit_log)
  - FastAPI app with lifespan-driven Alembic migration runner (asyncio.to_thread pattern)
  - Async SQLAlchemy engine + session factory + get_db dependency
  - Fernet encrypt_password / decrypt_password helpers
  - APIResponse[T] generic response envelope
  - ISAPIClient minimal extension point for Phase 2
  - pytest fixtures: engine, db_session, AsyncClient with get_db override
  - MockISAPIClient for unit tests
affects: [02-locations-nvrs-crud, 03-cameras-sync, 04-partitions-arming, 05-scheduler, 06-admin-ui]

# Tech tracking
tech-stack:
  added:
    - fastapi>=0.115
    - sqlalchemy[asyncio]>=2.0 (Mapped[T] + mapped_column() style)
    - asyncpg>=0.29
    - alembic>=1.13 (async template)
    - pydantic-settings>=2.0
    - cryptography>=42.0 (Fernet)
    - httpx>=0.27
    - pytest-asyncio>=0.23
    - lxml>=5.0
  patterns:
    - async_sessionmaker with expire_on_commit=False
    - asyncio.to_thread for Alembic in async lifespan
    - get_db dependency injection via Depends()
    - function-scoped engine fixture with create_all/drop_all isolation
    - connection-level transaction + rollback for test db_session isolation

key-files:
  created:
    - pyproject.toml
    - .env.example
    - app/main.py
    - app/core/config.py
    - app/core/database.py
    - app/core/crypto.py
    - app/core/schemas.py
    - app/locations/models.py
    - app/nvrs/models.py
    - app/cameras/models.py
    - app/partitions/models.py
    - app/isapi/client.py
    - alembic.ini
    - alembic/env.py
    - alembic/versions/0001_initial_schema.py
    - tests/conftest.py
    - tests/mocks.py
    - tests/test_core.py
    - tests/test_schema.py
  modified:
    - pyproject.toml (added tool.setuptools.packages.find to fix multi-package discovery)

key-decisions:
  - "Use asyncio.to_thread for Alembic upgrade in FastAPI lifespan (avoids threading.local context loss)"
  - "expire_on_commit=False on async_sessionmaker prevents MissingGreenlet errors post-commit"
  - "GENERATED ALWAYS AS STORED for disarm_count added via raw ALTER TABLE SQL (SQLAlchemy Computed() has asyncpg issues)"
  - "Removed deprecated op.get_bind() pattern for enum type creation; let op.create_table handle it automatically"
  - "Function-scoped engine fixture for tests (not session-scoped) to avoid asyncio event loop / asyncpg pool mismatch with pytest-asyncio 0.23.x"
  - "tool.setuptools.packages.find include=[app*] required to disambiguate multi-package layout for pip editable install"

patterns-established:
  - "Pattern: All DB models use SQLAlchemy 2.0 Mapped[T] + mapped_column() (not legacy Column())"
  - "Pattern: APIResponse[T] envelope used for all endpoints from Phase 1 onward"
  - "Pattern: ISAPIClient class designed as extension point - Phase 2 extends, does not restructure"
  - "Pattern: Test db_session uses connection.begin() + rollback() for isolation without truncate"

requirements-completed: [DATA-01, DATA-02, DATA-03, DATA-04, DATA-05, DATA-06, DATA-07, DATA-08, DATA-09]

# Metrics
duration: 15min
completed: 2026-03-10
---

# Phase 1 Plan 01: Foundation Summary

**FastAPI app with 9-table PostgreSQL schema via single Alembic migration, async SQLAlchemy 2.0 ORM, Fernet-encrypted NVR passwords, and complete pytest fixture infrastructure**

## Performance

- **Duration:** ~15 min (execution; code pre-existed from prior TDD sessions)
- **Started:** 2026-03-10T13:17:03Z
- **Completed:** 2026-03-10T13:18:26Z
- **Tasks:** 2
- **Files modified:** 20 (created) + 2 (fixed)

## Accomplishments

- All 9 SQLAlchemy 2.0 ORM models using Mapped[T] + mapped_column() syntax with native PostgreSQL types (ARRAY, JSONB, enum)
- Single Alembic migration creating all 9 tables in FK-dependency order; GENERATED ALWAYS AS STORED column for disarm_count via raw SQL; migration cycle (upgrade/downgrade/upgrade) verified clean
- FastAPI app auto-migrates on startup via asyncio.to_thread(_run_migrations) in lifespan context
- Test infrastructure: function-scoped engine fixtures with create_all/drop_all, connection-level rollback isolation, AsyncClient with get_db dependency override
- 15/15 tests passing (6 core behavior + 9 schema integration)

## Task Commits

Each task was committed atomically:

1. **Task 1: Project scaffold, core infrastructure, and all ORM models** - `7b87a40` (feat)
2. **Task 2: Alembic migration for all 9 tables and schema tests** - `e46ae35` (feat)

_Note: TDD history from prior sessions: `547d961` (failing tests), `965be57` (green), `4464f4d` (schema tests), then this session fixed blocking issues_

## Files Created/Modified

- `pyproject.toml` - Project metadata, dependencies, setuptools discovery, pytest config
- `.env.example` - Environment variable template
- `app/main.py` - FastAPI app with asyncio.to_thread lifespan migration runner
- `app/core/config.py` - pydantic-settings BaseSettings with DATABASE_URL, ENCRYPTION_KEY
- `app/core/database.py` - Async engine, async_sessionmaker (expire_on_commit=False), get_db
- `app/core/crypto.py` - Fernet encrypt_password / decrypt_password
- `app/core/schemas.py` - APIResponse[T] generic envelope
- `app/locations/models.py` - Location ORM model
- `app/nvrs/models.py` - NVRDevice ORM model
- `app/cameras/models.py` - Camera ORM model with UniqueConstraint(nvr_id, channel_no)
- `app/partitions/models.py` - Partition, PartitionCamera, PartitionState, CameraDetectionSnapshot, CameraDisarmRefcount (DDL event for generated column), PartitionAuditLog
- `app/isapi/client.py` - Minimal ISAPIClient with get_device_info / get_camera_channels
- `alembic.ini` - Alembic configuration
- `alembic/env.py` - Async Alembic env importing all models for autogenerate detection
- `alembic/versions/0001_initial_schema.py` - Single migration for all 9 tables
- `tests/conftest.py` - engine, db_session, client fixtures
- `tests/mocks.py` - MockISAPIClient
- `tests/test_core.py` - 6 core behavior tests
- `tests/test_schema.py` - 9 schema integration tests

## Decisions Made

- Used `asyncio.to_thread` for Alembic in FastAPI lifespan — prevents threading.local context loss with newer Alembic/asyncpg
- `expire_on_commit=False` on `async_sessionmaker` — prevents MissingGreenlet errors after commit in async context
- `disarm_count` added via raw `ALTER TABLE ... ADD COLUMN ... GENERATED ALWAYS AS STORED` SQL — SQLAlchemy Computed() has known asyncpg compatibility issues
- Function-scoped engine fixture instead of session-scoped — avoids asyncio event loop / asyncpg connection pool mismatch in pytest-asyncio 0.23.x

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed pyproject.toml multi-package discovery error**
- **Found during:** Task 1 verification (`pip install -e ".[test]"`)
- **Issue:** setuptools auto-discovery found both `app/` and `alembic/` as top-level packages, refused to build with "Multiple top-level packages discovered"
- **Fix:** Added `[tool.setuptools.packages.find]` with `include = ["app*"]` to pyproject.toml
- **Files modified:** `pyproject.toml`
- **Verification:** `pip install -e ".[test]"` succeeded cleanly
- **Committed in:** `7b87a40` (Task 1 commit)

**2. [Rule 1 - Bug] Fixed Alembic enum type duplicate creation error**
- **Found during:** Task 2 verification (`alembic upgrade head`)
- **Issue:** Migration used deprecated `partition_state_enum.create(op.get_bind())` + `create_type=False` pattern; newer Alembic/asyncpg 1.18.x caused the enum type to be created twice (once by explicit call, once by SQLAlchemy during table DDL), resulting in `DuplicateObjectError`
- **Fix:** Removed the explicit `partition_state_enum.create(op.get_bind())` call; let `op.create_table` handle enum creation via default `create_type=True`. Also replaced `enum.drop(op.get_bind())` in downgrade with `op.execute(sa.text("DROP TYPE partition_state_enum"))` to avoid deprecated pattern
- **Files modified:** `alembic/versions/0001_initial_schema.py`
- **Verification:** `alembic upgrade head`, `alembic downgrade base`, `alembic upgrade head` all complete without errors
- **Committed in:** `e46ae35` (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (1 blocking install error, 1 migration bug)
**Impact on plan:** Both fixes required for plan completion. No scope creep. Pattern for enum handling established for future migrations.

## Issues Encountered

- Alembic 1.18.x changed behavior around deprecated `op.get_bind()` causing enum type duplication. Fixed by relying on SQLAlchemy's built-in enum lifecycle management within `op.create_table`.

## User Setup Required

None - no external service configuration required beyond what's in `.env.example`.

## Next Phase Readiness

- All 9 tables available for Plans 02 and 03 (locations/NVR CRUD and camera sync)
- `tests/conftest.py` fixtures (engine, db_session, client) ready for reuse across all subsequent test files
- `app/isapi/client.py` designed as extension point — Phase 2 adds Digest auth retry, arm/disarm operations without restructuring
- `app/core/crypto.py` ready for NVR password encryption in Plan 02
- `alembic upgrade head` runs automatically on app startup — zero manual migration steps required

## Self-Check: PASSED

All key files verified present on disk. Both task commits verified in git history (7b87a40, e46ae35).

---
*Phase: 01-foundation*
*Completed: 2026-03-10*
