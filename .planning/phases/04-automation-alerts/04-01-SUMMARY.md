---
phase: 04-automation-alerts
plan: 01
subsystem: jobs
tags: [apscheduler, asyncio, postgresql, webhooks, httpx, background-jobs]

requires:
  - phase: 03-partition-api
    provides: arm_partition/disarm_partition service functions; PartitionState with scheduled_rearm_at field

provides:
  - app/jobs/ module with AsyncScheduler backed by SQLAlchemyDataStore
  - schedule_rearm() / cancel_rearm() helpers for scheduler integration
  - auto_rearm_job() — one-shot job that arms a partition and fires webhook
  - deliver_webhook() — POST with 3-retry backoff, non-blocking via asyncio.create_task
  - Startup reconciliation re-registers any missed rearm jobs from DB state
  - ALERT_WEBHOOK_URL optional setting in app/core/config.py

affects:
  - 04-02 (stuck monitor and NVR health check jobs — same scheduler instance)
  - 05-admin-ui (webhook delivery outcome visible via audit log)

tech-stack:
  added:
    - apscheduler[asyncpg]==4.0.0a6 (AsyncScheduler, SQLAlchemyDataStore, DateTrigger)
  patterns:
    - Deferred import of arm_partition inside auto_rearm_job body to break circular import
    - autouse pytest fixture to mock schedule_rearm/cancel_rearm in all API/integration tests
    - asyncio.create_task for fire-and-forget webhook delivery

key-files:
  created:
    - app/jobs/__init__.py
    - app/jobs/scheduler.py
    - app/jobs/auto_rearm.py
    - tests/test_jobs_auto_rearm.py
  modified:
    - app/main.py
    - app/partitions/service.py
    - app/core/config.py
    - tests/conftest.py

key-decisions:
  - "APScheduler 4.x uses add_schedule (not add_job) with DateTrigger for one-shot jobs; ConflictPolicy.replace handles re-scheduling"
  - "cancel_rearm catches ScheduleLookupError (not JobLookupError) — APScheduler 4.x exception for missing schedules"
  - "deliver_webhook retry: 4 total attempts (1 initial + 3 retries) with asyncio.sleep delays [1, 5, 15]s; ALERT_WEBHOOK_URL=None skips delivery silently"
  - "autouse conftest fixture mocks schedule_rearm/cancel_rearm at service module level for all non-job tests to prevent RuntimeError from unstarted scheduler"
  - "Startup reconciliation uses get_schedule() with try/except to detect missing schedules — APScheduler 4.x has no 'schedule exists' check API"

patterns-established:
  - "Deferred import pattern: arm_partition imported inside auto_rearm_job body (not module-level) to prevent circular dependency"
  - "Scheduler mock fixture: autouse conftest fixture patches service-level imports, not the scheduler module, for test isolation"

requirements-completed:
  - JOB-01
  - ALRT-01

duration: 12min
completed: 2026-03-11
---

# Phase 4 Plan 1: APScheduler Auto-Rearm Job Summary

**APScheduler 4.x with PostgreSQL job store wired into FastAPI lifespan; auto-rearm background job calls arm_partition with performed_by='system:auto_rearm' and fires webhook with retry backoff**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-03-11T00:00:00Z
- **Completed:** 2026-03-11T00:12:00Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments

- Created `app/jobs/` module with `AsyncScheduler` backed by `SQLAlchemyDataStore` (PostgreSQL) so job schedules survive restarts
- `schedule_rearm` / `cancel_rearm` helpers wired into `disarm_partition` and `arm_partition` service functions
- `auto_rearm_job` opens its own DB session and calls `arm_partition` with `performed_by='system:auto_rearm'`; webhook fires as `asyncio.create_task`
- `deliver_webhook` retries up to 3 times with [1, 5, 15]s delays, logs failure, never raises
- FastAPI lifespan starts/stops scheduler and reconciles missed rearm jobs on startup
- All 106 tests pass (96 pre-existing + 10 new job unit tests)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add APScheduler dependency and create app/jobs/ module** - `2f9875f` (feat + test — TDD)
2. **Task 2: Wire scheduler into FastAPI lifespan and hook schedule/cancel into disarm/arm service** - `e9bc644` (feat)

## Files Created/Modified

- `app/jobs/__init__.py` - Package init for jobs module
- `app/jobs/scheduler.py` - Shared AsyncScheduler instance; start_scheduler/shutdown_scheduler lifespan helpers
- `app/jobs/auto_rearm.py` - schedule_rearm, cancel_rearm, auto_rearm_job, deliver_webhook
- `tests/test_jobs_auto_rearm.py` - 10 unit tests covering schedule/cancel/fire/webhook behaviors
- `app/main.py` - Scheduler start/stop in lifespan; startup reconciliation of missed rearm jobs
- `app/partitions/service.py` - schedule_rearm after disarm commit; cancel_rearm before arm writes
- `app/core/config.py` - Added ALERT_WEBHOOK_URL optional setting
- `tests/conftest.py` - autouse fixture to mock schedule_rearm/cancel_rearm in API tests

## Decisions Made

- **APScheduler 4.x API**: The plan referenced `add_job` with `DateTrigger`, but APScheduler 4.x uses `add_schedule` for triggered (one-shot or recurring) jobs; `add_job` is for immediate one-off execution. Used `add_schedule` with `DateTrigger` and `ConflictPolicy.replace` for idempotent re-scheduling.
- **ScheduleLookupError vs JobLookupError**: APScheduler 4.x raises `ScheduleLookupError` when removing a non-existent schedule (not `JobLookupError`). `cancel_rearm` catches `ScheduleLookupError`.
- **Test isolation strategy**: Added `autouse=True` conftest fixture patching `app.partitions.service.schedule_rearm` and `cancel_rearm` — patches at the service import site so existing arm/disarm API tests aren't impacted by scheduler initialization requirements.
- **Startup reconciliation**: Uses `scheduler.get_schedule(job_id)` wrapped in try/except since APScheduler 4.x has no `.has_schedule()` method.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] APScheduler 4.x uses add_schedule, not add_job, for DateTrigger jobs**
- **Found during:** Task 1 (implementation)
- **Issue:** Plan specified `scheduler.add_job(auto_rearm_job, DateTrigger(...), id=..., replace_existing=True, kwargs=...)` but APScheduler 4.x `add_job` has no trigger parameter — it runs immediately. `add_schedule` is the correct method for triggered execution.
- **Fix:** Used `scheduler.add_schedule(auto_rearm_job, DateTrigger(run_time=run_at), id=..., kwargs=..., conflict_policy=ConflictPolicy.replace)`. Also replaced `replace_existing=True` with `conflict_policy=ConflictPolicy.replace` (4.x API).
- **Files modified:** app/jobs/auto_rearm.py
- **Verification:** Unit test `test_schedule_rearm_replaces_existing_job` passes
- **Committed in:** 2f9875f (Task 1 commit)

**2. [Rule 3 - Blocking] Existing arm/disarm API tests failed due to unstarted scheduler**
- **Found during:** Task 2 (verification of pre-existing tests)
- **Issue:** `cancel_rearm` raises `RuntimeError: The scheduler has not been initialized yet` when called during API tests that use the test DB but no running scheduler.
- **Fix:** Added `autouse=True` fixture in `tests/conftest.py` that patches `app.partitions.service.schedule_rearm` and `cancel_rearm` with AsyncMock for all tests except `test_jobs_auto_rearm.py` (which manages its own mocks).
- **Files modified:** tests/conftest.py
- **Verification:** All 106 tests pass
- **Committed in:** e9bc644 (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (1 bug — API mismatch, 1 blocking — test isolation)
**Impact on plan:** Both fixes necessary for correctness and test suite integrity. No scope creep.

## Issues Encountered

- APScheduler 4.0.0a6 required `sniffio` and `anyio` as transitive dependencies not bundled with the `[asyncpg]` extra — installed separately. No code changes needed.

## Next Phase Readiness

- Scheduler module ready for phase 04-02 (stuck-disarmed monitor and NVR health check jobs) — same `scheduler` instance from `app.jobs.scheduler`
- `deliver_webhook` is reusable for all 3 webhook types (auto_rearmed, stuck_disarmed, nvr_offline/online)
- `ALERT_WEBHOOK_URL` setting available; just needs to be set in `.env`

---
*Phase: 04-automation-alerts*
*Completed: 2026-03-11*
