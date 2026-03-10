---
phase: 02-isapi-core-operations
plan: 01
subsystem: api
tags: [httpx, isapi, hikvision, digest-auth, retry-logic, tdd]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: ISAPIClient base class with get_device_info and get_camera_channels

provides:
  - ISAPIClient.get_detection_config(channel_no, detection_type) -> str
  - ISAPIClient.put_detection_config(channel_no, detection_type, xml_body) -> None
  - ISAPIClient._detection_url helper for ISAPI/Smart URL construction
  - Single-retry-on-timeout logic for all detection calls
  - MockISAPIClient stubs for both new methods

affects:
  - 02-02 (disarm operation — reads detection config per camera)
  - 02-03 (arm operation — writes detection config to restore snapshots)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "retry-on-timeout: try/except httpx.TimeoutException with one retry; non-timeout errors raise immediately"
    - "detection URL helper: _detection_url(channel_no, detection_type) -> /ISAPI/Smart/{type}/channels/{no}"
    - "AsyncClient context manager per call (stateless, credentials in _client_kwargs)"

key-files:
  created:
    - tests/test_isapi_client.py
  modified:
    - app/isapi/client.py
    - tests/mocks.py

key-decisions:
  - "httpx.Timeout requires positional default arg in 0.28+ — fixed Timeout(connect=5.0, read=10.0) to Timeout(10.0, connect=5.0, read=10.0)"
  - "Retry implemented inline (try/except) rather than a decorator — simpler for single-retry-only semantics with no complexity creep"
  - "Non-timeout errors pass through raise_for_status() with no retry — 4xx/5xx are NVR errors that retrying would not fix"

patterns-established:
  - "Detection methods open a fresh AsyncClient context per call — matches existing get_device_info pattern"
  - "PUT sends content=xml_body.encode() with Content-Type text/xml header — matches Hikvision ISAPI write contract"

requirements-completed: [ISAPI-01, ISAPI-02, ISAPI-03, ISAPI-04, ISAPI-05]

# Metrics
duration: 10min
completed: 2026-03-10
---

# Phase 2 Plan 01: ISAPI Detection Config Methods Summary

**ISAPIClient extended with get_detection_config/put_detection_config and single-retry-on-timeout logic for all 4 Hikvision detection endpoint types**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-03-10T14:00:00Z
- **Completed:** 2026-03-10T14:10:00Z
- **Tasks:** 1 (TDD: RED commit + GREEN commit)
- **Files modified:** 3

## Accomplishments

- Implemented `get_detection_config(channel_no, detection_type)` returning raw XML on 200
- Implemented `put_detection_config(channel_no, detection_type, xml_body)` returning None on 200
- Single retry on `httpx.TimeoutException` only; non-timeout errors raise immediately
- Verified all 4 detection types (MotionDetection, LineDetection, FieldDetection, shelteralarm)
- Extended `MockISAPIClient` with matching stubs for downstream test use
- Fixed pre-existing `httpx.Timeout` constructor bug (Rule 1 auto-fix)

## Task Commits

TDD execution — each phase committed separately:

1. **RED — Failing tests** - `5b8b67d` (test)
2. **GREEN — Implementation** - `9fc2244` (feat)

## Files Created/Modified

- `app/isapi/client.py` — Added `_detection_url`, `get_detection_config`, `put_detection_config`; fixed `httpx.Timeout` constructor call
- `tests/test_isapi_client.py` — New file; 10 tests covering GET/PUT success, timeout retry, non-timeout immediate raise, all detection types
- `tests/mocks.py` — Added `get_detection_config` and `put_detection_config` stubs to `MockISAPIClient`

## Decisions Made

- **Retry inline vs decorator:** Single-retry semantics are simple enough that a try/except block inside each method is clearer than a general decorator.
- **No retry on non-timeout errors:** 4xx/5xx indicate NVR-side rejections; retrying would not change the outcome and could obscure errors.
- **httpx.Timeout positional arg:** httpx 0.28.1 requires `Timeout(default, connect=..., read=...)` — the pre-existing code used keyword-only form which raises ValueError.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed httpx.Timeout constructor incompatibility**
- **Found during:** Task 1 (RED phase — tests errored before even hitting AttributeError)
- **Issue:** `httpx.Timeout(connect=5.0, read=10.0)` raises `ValueError` in httpx 0.28.1 — a positional default is required when not setting all four params explicitly
- **Fix:** Changed to `httpx.Timeout(10.0, connect=5.0, read=10.0)` — default 10s with connect/read overrides
- **Files modified:** `app/isapi/client.py`
- **Verification:** Tests now error only on missing methods (AttributeError), not on client init; full suite passes after implementation
- **Committed in:** `9fc2244` (GREEN phase commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug)
**Impact on plan:** Required fix — without it no tests could run. No scope creep.

## Issues Encountered

None — implementation matched plan specification exactly after fixing the httpx.Timeout bug.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `ISAPIClient.get_detection_config` and `put_detection_config` ready for use in Phase 2 Plan 02 (disarm) and Plan 03 (arm)
- `MockISAPIClient` stubs allow downstream tests to run without NVR network access
- No blockers

---
*Phase: 02-isapi-core-operations*
*Completed: 2026-03-10*
