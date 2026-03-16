---
phase: 07-isapi-retry-fix
plan: 01
subsystem: api
tags: [httpx, isapi, retry, fastapi, apscheduler, config]

# Dependency graph
requires:
  - phase: 02-isapi-core-operations
    provides: ISAPIClient with retry pattern on get_detection_config and put_detection_config
  - phase: 04-automation-alerts
    provides: stuck_disarmed_monitor APScheduler job registered in lifespan
  - phase: 05-admin-ui
    provides: ui/routes.py with self-call pattern to internal API
provides:
  - ISAPI-03 fully satisfied: all four ISAPIClient methods retry once on TimeoutException
  - Zero hardcoded localhost:8000 strings in app/ui/routes.py
  - POLL_INTERVAL_SECONDS config var drives stuck_disarmed_monitor scheduler interval
affects: [08-release, isapi, ui, scheduler]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Inline try/except httpx.TimeoutException retry (no decorator, no tenacity) — single-retry-only semantics"
    - "settings.BASE_URL for all internal self-call URLs in UI routes"
    - "IntervalTrigger(seconds=settings.POLL_INTERVAL_SECONDS) for config-driven scheduler interval"

key-files:
  created: []
  modified:
    - app/isapi/client.py
    - app/ui/routes.py
    - app/main.py
    - .env.example
    - tests/test_isapi_client.py
    - tests/test_jobs_monitors.py

key-decisions:
  - "Inline try/except retry applied to get_device_info and get_camera_channels — matches existing codebase pattern, no new abstractions"
  - "Test for stuck_disarmed_monitor interval updated from trigger.minutes==5 to trigger.seconds==settings.POLL_INTERVAL_SECONDS to reflect new config-driven behavior"

patterns-established:
  - "All ISAPIClient methods use inline try/except httpx.TimeoutException for single retry"
  - "All UI self-calls use settings.BASE_URL — no hardcoded host:port strings"

requirements-completed: [ISAPI-03]

# Metrics
duration: 3min
completed: 2026-03-16
---

# Phase 7 Plan 01: ISAPI Retry Fix Summary

**Inline retry-on-timeout added to all four ISAPIClient methods; hardcoded localhost:8000 replaced with settings.BASE_URL in ui/routes.py; POLL_INTERVAL_SECONDS wired to stuck_disarmed_monitor scheduler — 158 tests green**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-16T10:32:39Z
- **Completed:** 2026-03-16T10:35:47Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- ISAPI-03 now fully covered: get_device_info and get_camera_channels both retry once on TimeoutException (matching existing get_detection_config / put_detection_config pattern)
- 4 new unit tests for get_device_info and get_camera_channels retry behavior (TDD: RED then GREEN)
- All 4 hardcoded `http://localhost:8000` strings in ui/routes.py replaced with `settings.BASE_URL` — deployments on non-localhost hosts now work correctly
- POLL_INTERVAL_SECONDS (previously inert config var) now drives the stuck_disarmed_monitor APScheduler interval

## Task Commits

Each task was committed atomically:

1. **Task 1: Add retry to get_device_info and get_camera_channels with tests** - `1b495f8` (feat)
2. **Task 2: Fix BASE_URL in ui/routes.py and wire POLL_INTERVAL_SECONDS in main.py** - `0372d09` (fix)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified

- `app/isapi/client.py` - Added inline try/except httpx.TimeoutException retry blocks to get_device_info and get_camera_channels
- `tests/test_isapi_client.py` - Added 4 new tests: double-timeout raises + first-timeout-then-success for both get_device_info and get_camera_channels
- `app/ui/routes.py` - Added `from app.core.config import settings` import; replaced 4 hardcoded localhost:8000 URLs with settings.BASE_URL
- `app/main.py` - Changed IntervalTrigger(minutes=5) to IntervalTrigger(seconds=settings.POLL_INTERVAL_SECONDS) for stuck_disarmed_monitor
- `.env.example` - Updated POLL_INTERVAL_SECONDS comment to note it is now actively wired to the scheduler
- `tests/test_jobs_monitors.py` - Updated test_lifespan_registers_stuck_disarmed_monitor test to assert trigger.seconds==settings.POLL_INTERVAL_SECONDS instead of trigger.minutes==5

## Decisions Made

- Inline try/except retry applied to get_device_info and get_camera_channels — matches existing codebase pattern established in Phase 02; no decorator or tenacity introduced
- Test for stuck_disarmed_monitor interval updated from `trigger.minutes==5` to `trigger.seconds==settings.POLL_INTERVAL_SECONDS` to reflect new config-driven behavior — this was a required consequence of the main.py fix

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated test_jobs_monitors test to match new POLL_INTERVAL_SECONDS behavior**
- **Found during:** Task 2 (Fix BASE_URL in ui/routes.py and wire POLL_INTERVAL_SECONDS in main.py)
- **Issue:** `test_lifespan_registers_stuck_disarmed_monitor_with_5_minute_interval` asserted `trigger.minutes == 5` which fails after changing to `IntervalTrigger(seconds=settings.POLL_INTERVAL_SECONDS)`
- **Fix:** Renamed test to `test_lifespan_registers_stuck_disarmed_monitor_with_poll_interval_seconds` and updated assertion to check `trigger.seconds == settings.POLL_INTERVAL_SECONDS`
- **Files modified:** tests/test_jobs_monitors.py
- **Verification:** Full test suite 158 tests green
- **Committed in:** `0372d09` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug — test reflecting old hardcoded behavior)
**Impact on plan:** Necessary to keep test suite accurate after intentional implementation change. No scope creep.

## Issues Encountered

None — both tasks executed cleanly on first attempt.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All v1.0 audit gaps from Phase 7 research are now closed
- ISAPI-03 requirement fully satisfied across all four ISAPIClient methods
- Deployment on any host now works correctly via BASE_URL configuration
- 158 tests passing — ready for release phase

---
*Phase: 07-isapi-retry-fix*
*Completed: 2026-03-16*
