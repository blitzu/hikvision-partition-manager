---
phase: 04-automation-alerts
plan: 02
subsystem: api
tags: [apscheduler, asyncio, webhooks, monitoring, background-jobs, pytest-asyncio]

requires:
  - phase: 04-automation-alerts plan 01
    provides: deliver_webhook(), scheduler instance, APScheduler lifespan integration

provides:
  - stuck_disarmed_monitor(): every-5-minute job that fires partition_stuck_disarmed webhooks per overdue partition
  - nvr_health_check(): every-60-second job that updates NVR status and fires nvr_offline/nvr_online transition webhooks
  - Both jobs registered into APScheduler scheduler via add_schedule + IntervalTrigger in app/main.py lifespan

affects:
  - 05-admin-ui (admin dashboard shows NVR status and partition overdue flags — data driven by these monitors)

tech-stack:
  added: []
  patterns:
    - "Module-level dicts for stateful job tracking across scheduler cycles (_nvr_prev_status, _nvr_last_offline_alert)"
    - "asyncio.create_task wraps deliver_webhook for non-blocking webhook delivery from sync job functions"
    - "IntervalTrigger + ConflictPolicy.replace for idempotent recurring job registration on startup"
    - "TDD: failing test committed (RED), implementation committed separately (GREEN)"

key-files:
  created:
    - app/jobs/monitors.py
    - tests/test_jobs_monitors.py
  modified:
    - app/main.py

key-decisions:
  - "APScheduler 4.x uses add_schedule (not add_job) with IntervalTrigger for recurring jobs — plan spec had add_job which was corrected (Rule 1 auto-fix)"
  - "nvr_offline cooldown re-fires after 5-minute cooldown even when already-offline (continuous suppressed re-alerting pattern)"
  - "prev_status initialized from nvr.status (DB value) when first seen — avoids false offline alerts for NVRs that were offline before process start"

patterns-established:
  - "Monitor jobs open their own session via async_session_factory() — no session injection"
  - "Module-level state dicts reset via .clear() in tests to ensure test isolation"

requirements-completed: [JOB-02, JOB-03, ALRT-02, ALRT-03]

duration: 6min
completed: 2026-03-11
---

# Phase 4 Plan 02: Monitors Summary

**Stuck-disarmed and NVR health-check monitors using APScheduler IntervalTrigger, with offline cooldown suppression and online recovery webhooks**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-11T05:31:11Z
- **Completed:** 2026-03-11T05:37:14Z
- **Tasks:** 2 (Task 1 had TDD: test + impl commits)
- **Files modified:** 3

## Accomplishments
- stuck_disarmed_monitor fires partition_stuck_disarmed webhooks per overdue disarmed partition, every 5 minutes, indefinitely until rearmed
- nvr_health_check pings all NVRs via ISAPIClient every 60s, updates status/last_seen_at, fires nvr_offline (with 5-min cooldown) and nvr_online (recovery) webhooks
- Both monitors registered into APScheduler on startup using IntervalTrigger + ConflictPolicy.replace
- 11 tests covering all behavior: overdue detection, skip non-overdue, multi-partition, offline/online transitions, cooldown suppression, cooldown expiry, stable-online no-webhook, last_seen_at update, DB commit

## Task Commits

Each task was committed atomically:

1. **Task 1 (TDD RED): Failing tests** - `7664a57` (test)
2. **Task 1 (TDD GREEN): monitors.py implementation** - `dd8b788` (feat)
3. **Task 2: Register monitors in scheduler** - `36cdda8` (feat)

**Plan metadata:** (docs commit follows)

_Note: TDD task had separate test and implementation commits._

## Files Created/Modified
- `app/jobs/monitors.py` - stuck_disarmed_monitor and nvr_health_check job functions with module-level state tracking
- `tests/test_jobs_monitors.py` - 11 unit tests for all monitor behaviors (mocked DB, ISAPIClient, deliver_webhook)
- `app/main.py` - Imports and registers both monitor jobs in lifespan via add_schedule + IntervalTrigger

## Decisions Made
- **APScheduler add_schedule vs add_job:** Plan spec had `add_job` with `IntervalTrigger` — actual APScheduler 4.x API uses `add_schedule` for recurring jobs. Fixed automatically (Rule 1 auto-fix).
- **Cooldown re-fire:** When an NVR remains offline past the 5-minute cooldown, the job re-fires nvr_offline. This matches the plan spec: "NVR offline alerts are suppressed if the same NVR already fired within the last 5 minutes" — implying re-fire after cooldown.
- **prev_status init from DB status:** When an NVR is first seen by the job, prev_status is seeded from the DB status field to avoid false online/offline transitions on restart.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Used add_schedule instead of add_job for interval scheduling**
- **Found during:** Task 2 (scheduler registration)
- **Issue:** Plan spec showed `scheduler.add_job(func, IntervalTrigger(...), id=..., replace_existing=True)` but APScheduler 4.x `add_job` doesn't accept a trigger or id — it runs a one-off job. `add_schedule` is the correct API for recurring scheduled jobs.
- **Fix:** Used `scheduler.add_schedule(func, IntervalTrigger(...), id=..., conflict_policy=ConflictPolicy.replace)` matching the APScheduler 4.x API established in Plan 01.
- **Files modified:** app/main.py
- **Verification:** `from app.main import app` succeeds, 108 tests pass
- **Committed in:** 36cdda8 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — APScheduler API mismatch)
**Impact on plan:** Required for correct behavior — add_job doesn't register recurring interval schedules.

## Issues Encountered
None beyond the APScheduler API deviation documented above.

## User Setup Required
None - no external service configuration required beyond ALERT_WEBHOOK_URL already documented in Plan 01.

## Next Phase Readiness
- All automation/alert jobs now running: auto-rearm (Plan 01), stuck-disarmed (Plan 02), NVR health (Plan 02)
- Requirements JOB-01 through JOB-03 and ALRT-01 through ALRT-03 fully satisfied
- Phase 4 complete — ready for Phase 5 (Admin UI)

---
*Phase: 04-automation-alerts*
*Completed: 2026-03-11*
