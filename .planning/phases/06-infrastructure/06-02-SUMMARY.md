---
phase: 06-infrastructure
plan: "02"
subsystem: infra
tags: [logging, middleware, graceful-shutdown, inflight-drain, readme]

# Dependency graph
requires:
  - phase: 06-infrastructure
    plan: "01"
    provides: Dockerfile, docker-compose.yml, .env.example

provides:
  - app/core/logging.py (JsonFormatter + setup_logging)
  - app/middleware/logging.py (RequestLoggingMiddleware + request_id_var)
  - app/core/inflight.py (increment/decrement/wait_drain/track_inflight)
  - Updated app/main.py (logging, middleware, graceful shutdown)
  - Updated app/isapi/client.py (all 4 methods wrapped with inflight tracking)
  - README.md (Quick Start, VMS Integration Guide, Refcount, Troubleshooting)

affects: [observability, graceful-shutdown, documentation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - JsonFormatter with lazy request_id_var import to avoid circular dependency
    - Lazy asyncio.Event creation (inside running loop) to avoid Python 3.10+ DeprecationWarning
    - BaseHTTPMiddleware for per-request UUID injection and access logging
    - _track_inflight() async context manager wrapping all ISAPI calls
    - Manual logging.Handler in test (caplog cannot capture records from worker thread)

key-files:
  created:
    - app/core/logging.py
    - app/middleware/__init__.py
    - app/middleware/logging.py
    - app/core/inflight.py
    - README.md
    - tests/test_infra.py
  modified:
    - app/core/config.py
    - app/main.py
    - app/isapi/client.py

key-decisions:
  - "Lazy import of request_id_var inside JsonFormatter.format() avoids circular import between app.core.logging and app.middleware.logging"
  - "asyncio.Event() created lazily via _get_event() — Python 3.10+ raises DeprecationWarning when Event is created at module import time outside running loop"
  - "Manual logging.Handler in test_access_log_middleware instead of caplog — TestClient runs ASGI app in anyio portal worker thread, outside caplog propagation chain"
  - "setup_logging() called as module-level statement in app/main.py (before FastAPI) — this runs at import time, which is the earliest safe point in the app lifecycle"
  - "INFRA-07 audit: no f-string SQL interpolation found in app/ codebase — all queries use SQLAlchemy ORM"

# Metrics
duration: 8min
completed: 2026-03-11
---

# Phase 6 Plan 02: JSON Logging, Graceful Shutdown, and README Summary

**Structured JSON logging (JsonFormatter + RequestLoggingMiddleware), in-flight ISAPI call drain (inflight counter wired into ISAPIClient and lifespan), SQL injection audit (INFRA-07 clean), and comprehensive operator README**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-03-11T18:53:00Z
- **Completed:** 2026-03-11T19:01:29Z
- **Tasks:** 2 (+ 1 checkpoint auto-approved)
- **Files modified:** 9

## Accomplishments

- `app/core/logging.py`: `JsonFormatter` produces single-line JSON with timestamp, level, logger, message, request_id; scrubs `password` field (NVR-06); `setup_logging()` configures root logger
- `app/middleware/logging.py`: `RequestLoggingMiddleware` injects UUID per request via `ContextVar`; emits INFO access log with component, method, path, status_code, duration_ms
- `app/core/inflight.py`: lazy `asyncio.Event` counter with `increment()`, `decrement()`, `wait_drain(timeout)`, `track_inflight()` context manager, `reset()` for test isolation
- `app/main.py`: `setup_logging()` called before `FastAPI()`, `RequestLoggingMiddleware` registered, `wait_drain(30.0)` in lifespan shutdown before `engine.dispose()`
- `app/isapi/client.py`: all 4 ISAPI methods (`get_device_info`, `get_camera_channels`, `get_detection_config`, `put_detection_config`) wrapped with `_track_inflight()`
- `app/core/config.py`: added `POLL_INTERVAL_SECONDS: int = 300`
- `README.md`: Quick Start (3-step Docker setup), env vars table (6 vars), VMS Integration Guide (curl examples for arm/disarm/state/dashboard), Refcount ASCII diagram with edge cases, 5-entry Troubleshooting
- `tests/test_infra.py`: 8 test cases covering INFRA-03 (.env.example), INFRA-04 (drain + timeout), INFRA-05 (JsonFormatter fields + password scrub), INFRA-06 (access log + request_id) — all GREEN
- INFRA-07: `grep -rn "text(f" app/` returns no matches — SQL injection audit clean

## Task Commits

1. **Task 1: Structured JSON logging, request middleware, inflight drain** - `fde2e63` (feat)
2. **Task 2: Wire into main.py, audit SQL, write README** - `9b01873` (feat)

## Files Created/Modified

- `app/core/logging.py` - JsonFormatter + setup_logging()
- `app/middleware/__init__.py` - Package init
- `app/middleware/logging.py` - RequestLoggingMiddleware + request_id_var ContextVar
- `app/core/inflight.py` - Lazy Event counter for graceful shutdown drain
- `app/core/config.py` - Added POLL_INTERVAL_SECONDS: int = 300
- `app/main.py` - Wired logging, middleware, and wait_drain into lifespan
- `app/isapi/client.py` - All 4 ISAPI methods wrapped with _track_inflight()
- `README.md` - Comprehensive operator and developer documentation
- `tests/test_infra.py` - 8 infra test cases (all GREEN)

## Decisions Made

- Lazy import of `request_id_var` inside `JsonFormatter.format()` avoids circular import between `app.core.logging` and `app.middleware.logging`
- `asyncio.Event()` created lazily via `_get_event()` — Python 3.10+ raises DeprecationWarning when Event is created at module import time outside running loop
- Manual `logging.Handler` in `test_access_log_middleware` instead of `caplog` — `TestClient` runs ASGI app in anyio portal worker thread, outside caplog's propagation chain
- `setup_logging()` called as module-level statement in `app/main.py` (before `FastAPI()`) — earliest safe point in app lifecycle
- INFRA-07 audit: no f-string SQL interpolation in `app/` — all queries use SQLAlchemy ORM

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test_access_log_middleware using manual logging handler**
- **Found during:** Task 1 GREEN phase
- **Issue:** `caplog` fixture could not capture log records emitted by `RequestLoggingMiddleware` because `TestClient` (via anyio) runs the ASGI app in a worker thread, outside pytest's log capture propagation chain. The middleware was correctly emitting records (visible in stderr) but `caplog.records` remained empty.
- **Fix:** Replaced `caplog.at_level(...)` with a custom `logging.Handler` subclass attached directly to the `"http"` logger for the duration of the test. Handler is removed in a `finally` block.
- **Files modified:** `tests/test_infra.py`
- **Commit:** `fde2e63`

## Issues Encountered

None beyond the test capture fix above.

## User Setup Required

None.

## Self-Check

- [x] `app/core/logging.py` exists
- [x] `app/middleware/logging.py` exists
- [x] `app/core/inflight.py` exists
- [x] `README.md` exists
- [x] `tests/test_infra.py` exists (8 tests, all GREEN)
- [x] Commits `fde2e63` and `9b01873` exist

## Self-Check: PASSED
