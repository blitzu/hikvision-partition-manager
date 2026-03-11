---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: completed
stopped_at: Completed 06-infrastructure plan 02 — JSON logging, graceful shutdown drain, README
last_updated: "2026-03-11T19:05:58.665Z"
last_activity: 2026-03-11 — stuck-disarmed monitor + NVR health check APScheduler jobs (108 tests)
progress:
  total_phases: 6
  completed_phases: 6
  total_plans: 15
  completed_plans: 15
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-10)

**Core value:** Disarming a partition disables detection on all member cameras via ISAPI; arming restores exact saved state, respecting multi-partition refcount logic.
**Current focus:** Phase 4 - Automation & Alerts

## Current Position

Phase: 4 of 6 (Automation & Alerts) — Plan 2 of 2 complete
Plan: 2 complete in current phase
Status: Phase 4 complete — All monitor jobs (stuck-disarmed + NVR health check) implemented and registered
Last activity: 2026-03-11 — stuck-disarmed monitor + NVR health check APScheduler jobs (108 tests)

Progress: [██████████] 100%

## Performance Metrics

**Velocity:**
- Total plans completed: 7
- Average duration: ~7.6 min
- Total execution time: ~53 min

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-foundation | 3 | ~26 min | ~9 min |
| 02-isapi-core-operations | 3 | ~24 min | ~8 min |
| 03-partition-api | 1 | ~4 min | ~4 min |

**Recent Trend:**
- Last 5 plans: 3min, 10min, 7min, 7min, 4min
- Trend: Improving/Stable

*Updated after each plan completion*

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| Phase 01-foundation P01 | 15 min | 2 tasks | 20 files |
| Phase 01-foundation P02 | 8 min | 2 tasks | 7 files |
| Phase 01-foundation P03 | 3 min | 2 tasks | 6 files |
| Phase 02-isapi-core-operations P01 | 10 min | 1 task | 3 files |
| Phase 02-isapi-core-operations P02 | 7 min | 2 tasks | 5 files |
| Phase 02-isapi-core-operations P03 | 7 min | 1 task | 3 files |
| Phase 03-partition-api P01 | 4 min | 5 tasks | 6 files |
| Phase 03-partition-api P02 | 8 | 5 tasks | 4 files |
| Phase 03-partition-api P03-03 | 5 | 3 tasks | 6 files |
| Phase 04-automation-alerts P01 | 12 | 2 tasks | 8 files |
| Phase 04-automation-alerts P02 | 6 | 2 tasks | 3 files |
| Phase 05-admin-ui P01 | 18 | 3 tasks | 12 files |
| Phase 05-admin-ui P02 | 8 min | 2 tasks | 5 files |
| Phase 06-infrastructure P01 | 1 | 2 tasks | 3 files |
| Phase 06-infrastructure P02 | 8 | 2 tasks | 9 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Python + FastAPI for async ISAPI calls
- APScheduler in-process (no separate scheduler)
- PostgreSQL native arrays for disarmed_by_partitions refcount
- JSONB for detection snapshots (heterogeneous ISAPI XML responses)
- HTMX + Jinja2 + Pico CSS for admin UI (no SPA)
- [Phase 01-foundation]: asyncio.to_thread for Alembic upgrade in FastAPI lifespan prevents threading.local context loss
- [Phase 01-foundation]: expire_on_commit=False on async_sessionmaker prevents MissingGreenlet errors in async context
- [Phase 01-foundation]: GENERATED ALWAYS AS STORED for disarm_count added via raw ALTER TABLE SQL (Computed() has asyncpg issues)
- [Phase 01-foundation]: tool.setuptools.packages.find include=[app*] required for pip editable install with multi-package layout
- [Phase 01-foundation]: NVRRead uses structural field exclusion — password omitted from schema entirely, not via exclude= flag
- [Phase 01-foundation]: encrypt_password(body.password) called before NVRDevice ORM instantiation — plaintext never touches any model attribute
- [Phase 01-foundation]: Unknown FK returns APIResponse(success=False, error='Location not found') inside 200 envelope — consistent with response contract
- [Phase 01-foundation]: ISAPIClient pre-existed in app/isapi/client.py and matched plan spec exactly — used as-is
- [Phase 01-foundation]: monkeypatch.setattr on module ISAPIClient name chosen over DI parameter injection for minimal route API surface
- [Phase 01-foundation]: cameras router uses prefix=/api/nvrs to keep sync URL under /api/nvrs/{id}/cameras/sync without path duplication
- [Phase 02-isapi-core-operations]: httpx.Timeout requires positional default arg in 0.28+ — Timeout(10.0, connect=5.0, read=10.0)
- [Phase 02-isapi-core-operations]: Retry implemented inline (try/except) rather than a decorator — simpler for single-retry-only semantics
- [Phase 02-isapi-core-operations]: Non-timeout errors pass through raise_for_status() with no retry — 4xx/5xx are NVR-side errors
- [Phase 02-isapi-core-operations]: asyncio.Lock used in disarm_partition loop to prevent concurrent DB writes on the same AsyncSession from causing SAWarnings during parallel ISAPI calls.
- [Phase 02-isapi-core-operations]: Cameras that fail ALL 4 detection GETs result in an error; success in AT LEAST one type constitutes "found_any" success (partial-per-camera support).
- [Phase 02-isapi-core-operations]: Snapshot Immutability (DARM-04) implemented by copying existing snapshots from other partitions if available, ensuring the original armed state is always preserved.
- [Phase 03-partition-api]: soft-delete uses deleted_at nullable datetime on Partition; filtered via .is_(None) in all queries
- [Phase 03-partition-api]: deletion guard blocks DELETE if state is 'disarmed' or 'partial' — requires arm before delete
- [Phase 03-partition-api]: location validation in sync_partition_cameras uses camera -> NVR -> location_id chain; skipped if partition has no location_id
- [Phase 03-partition-api]: Pydantic ConfigDict(from_attributes=True) used over deprecated class Config pattern
- [Phase 03-partition-api]: Bulk-load snapshots and refcounts in get_partition_state using .in_() queries to avoid N+1 per camera
- [Phase 03-partition-api]: Audit log ordered newest-first (created_at.desc()); disarm_count derived from len(disarmed_by_partitions) at query time
- [Phase 03-partition-api]: dashboard_router uses prefix=/api so GET /api/dashboard has correct URL without duplicated prefix
- [Phase 03-partition-api]: disarmed_minutes computed at query time from state.last_changed_at — no stored field needed
- [Phase 03-partition-api]: overdue flag uses >= (at or past threshold triggers alert); active-first sort uses tuple key (priority_int, name)
- [Phase 04-automation-alerts]: APScheduler 4.x uses add_schedule (not add_job) with DateTrigger for one-shot jobs; ConflictPolicy.replace handles re-scheduling idempotently
- [Phase 04-automation-alerts]: cancel_rearm catches ScheduleLookupError (APScheduler 4.x) — not JobLookupError; autouse conftest fixture mocks service-level schedule_rearm/cancel_rearm for test isolation
- [Phase 04-automation-alerts]: IntervalTrigger + add_schedule used for recurring monitor jobs; add_job is one-shot only in APScheduler 4.x
- [Phase 04-automation-alerts]: Module-level dicts (_nvr_prev_status, _nvr_last_offline_alert) track NVR transition state across scheduler cycles; reset in tests via .clear()
- [Phase 04-automation-alerts]: nvr_offline cooldown re-fires after 5-minute window even when NVR stays offline (continuous suppressed-then-re-alert pattern)
- [Phase 05-admin-ui]: Two POST endpoint suffixes (-row vs -detail) for arm/disarm to serve correct partial for dashboard vs detail page context
- [Phase 05-admin-ui]: Native HTML <dialog> element used for modals — Pico CSS styles natively, no custom JS library needed
- [Phase 05-admin-ui]: rearm_in_minutes computed server-side in route handler to avoid datetime math in Jinja2 templates
- [Phase 05-admin-ui]: hx-vals JS expression collects checked camera_ids before Sync button fires — preserves selection across HTMX partial swap
- [Phase 05-admin-ui]: POST /ui/nvrs/create proxies to API endpoint to keep password encryption in one place
- [Phase 06-infrastructure]: python:3.12-slim (not alpine) for Docker base image — asyncpg requires glibc
- [Phase 06-infrastructure]: docker-compose stop_grace_period: 35s = 30s app timeout + 5s buffer; DATABASE_URL overridden in environment block to use service DNS hostname 'db'
- [Phase 06-infrastructure]: Lazy import of request_id_var inside JsonFormatter.format() avoids circular import between app.core.logging and app.middleware.logging
- [Phase 06-infrastructure]: asyncio.Event() created lazily in inflight module — Python 3.10+ DeprecationWarning when Event created outside running loop
- [Phase 06-infrastructure]: Manual logging.Handler in test_access_log_middleware — TestClient anyio portal thread runs outside caplog propagation chain

### Pending Todos

None yet.

### Blockers/Concerns

None yet.

## Session Continuity

Last session: 2026-03-11T19:02:35.127Z
Stopped at: Completed 06-infrastructure plan 02 — JSON logging, graceful shutdown drain, README
Resume file: None
