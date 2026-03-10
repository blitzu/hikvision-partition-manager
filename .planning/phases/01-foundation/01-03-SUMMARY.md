---
phase: 01-foundation
plan: 03
subsystem: api
tags: [fastapi, httpx, isapi, postgresql, pydantic, digest-auth]

# Dependency graph
requires:
  - phase: 01-foundation/01-01
    provides: "Database models (Camera, NVRDevice), Alembic migrations, async session factory"
  - phase: 01-foundation/01-02
    provides: "NVR CRUD routes, encrypt/decrypt_password, APIResponse envelope, conftest fixtures"
provides:
  - "ISAPIClient class in app/isapi/client.py — Phase 2 extension point for retry + detection endpoints"
  - "GET /api/nvrs/{id}/test — connectivity test returning deviceInfo or error envelope"
  - "GET /api/nvrs/{id}/cameras/sync — idempotent camera upsert via pg ON CONFLICT DO UPDATE"
  - "CameraRead Pydantic schema in app/cameras/schemas.py"
affects:
  - "02-isapi-integration"
  - "phase-2 detection endpoints"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "TDD red-green commit cycle per endpoint (failing tests committed before implementation)"
    - "PostgreSQL pg_insert ON CONFLICT DO UPDATE for idempotent upserts"
    - "monkeypatch.setattr for ISAPIClient injection in tests (no DI framework needed)"
    - "Always HTTP 200 with success=false envelope for ISAPI failures (never 5xx)"

key-files:
  created:
    - app/isapi/client.py
    - app/cameras/schemas.py
    - app/cameras/routes.py
    - tests/test_cameras.py
  modified:
    - app/nvrs/routes.py
    - app/main.py
    - tests/test_nvrs.py

key-decisions:
  - "ISAPIClient already existed in app/isapi/client.py from pre-plan work — used as-is, no restructure needed"
  - "monkeypatch.setattr on module-level ISAPIClient name chosen over DI parameter injection for minimal route API surface"
  - "cameras router uses prefix=/api/nvrs to keep sync URL under /api/nvrs/{id}/cameras/sync without path duplication"
  - "NVR status set to offline on ISAPI failure even when error is non-connectivity (e.g. parse error) — conservative approach"

patterns-established:
  - "Pattern: Error envelope — ISAPI failures always return HTTP 200 + success=false + type(exc).__name__ error"
  - "Pattern: NVR status lifecycle — unknown -> online (success) / offline (failure) after every ISAPI contact"
  - "Pattern: Upsert — pg_insert ON CONFLICT DO UPDATE with index_elements=[nvr_id, channel_no]"

requirements-completed:
  - NVR-03
  - NVR-04
  - NVR-05

# Metrics
duration: 3min
completed: 2026-03-10
---

# Phase 1 Plan 03: ISAPI Client, NVR Connectivity Test, and Camera Sync Summary

**Minimal ISAPIClient with httpx DigestAuth, GET /api/nvrs/{id}/test connectivity endpoint, and GET /api/nvrs/{id}/cameras/sync with PostgreSQL ON CONFLICT upsert — completing Phase 1 foundation**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-03-10T13:26:32Z
- **Completed:** 2026-03-10T13:29:14Z
- **Tasks:** 2 (both TDD)
- **Files modified:** 6

## Accomplishments

- Wired `GET /api/nvrs/{id}/test` into nvrs router — always HTTP 200, updates `last_seen_at`/`status` on ISAPI contact
- Created `GET /api/nvrs/{id}/cameras/sync` with PostgreSQL `ON CONFLICT DO UPDATE` ensuring double-sync never creates duplicate rows
- Verified ISAPIClient already existed in `app/isapi/client.py`; integrated it into both routes via `decrypt_password` pattern from Plan 02
- All 39 tests pass across locations, nvrs, cameras, core, and schema suites

## Task Commits

Each task was committed atomically using TDD red-green cycle:

1. **Task 1 RED: NVR connectivity tests** - `a996db7` (test)
2. **Task 1 GREEN: NVR connectivity endpoint** - `5aaf5aa` (feat)
3. **Task 2 RED: Camera sync tests** - `c32e7eb` (test)
4. **Task 2 GREEN: Camera sync endpoint** - `b330771` (feat)

_Note: TDD tasks have separate test → feat commits as required._

## Files Created/Modified

- `app/isapi/client.py` - Pre-existing ISAPIClient class; used as-is (Phase 2 extension point)
- `app/nvrs/routes.py` - Added `GET /api/nvrs/{id}/test` with ISAPIClient + last_seen_at update
- `app/cameras/schemas.py` - CameraRead Pydantic schema (from_attributes=True)
- `app/cameras/routes.py` - GET /api/nvrs/{id}/cameras/sync with pg_insert upsert
- `app/main.py` - Registered cameras_router
- `tests/test_nvrs.py` - Appended 5 connectivity tests (NVR-03, NVR-05)
- `tests/test_cameras.py` - Created with 6 camera sync tests (NVR-04, NVR-05)

## Decisions Made

- **ISAPIClient already existed**: `app/isapi/client.py` was already implemented from pre-plan scaffolding. Used as-is with no modifications; the existing implementation matched the plan spec exactly.
- **monkeypatch over DI injection**: Tests use `monkeypatch.setattr(routes, "ISAPIClient", ...)` rather than adding an optional factory parameter to routes. This keeps the route API surface minimal while enabling full test isolation.
- **cameras router prefix**: `APIRouter(prefix="/api/nvrs")` keeps the sync URL at `/api/nvrs/{id}/cameras/sync` without requiring path duplication in each route definition.
- **Offline on all ISAPI failures**: NVR status is set to `offline` on any exception (not just ConnectError) — conservative approach that flags the device for attention.

## Deviations from Plan

None - plan executed exactly as written. ISAPIClient was pre-built and matched the plan spec; no restructuring was needed.

## Issues Encountered

None. All tests passed on first implementation attempt for both tasks.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 1 is complete: locations CRUD + NVR CRUD + encryption + ISAPI connectivity + camera sync all implemented and tested
- ISAPIClient in `app/isapi/client.py` is ready for Phase 2 extension with retry logic, Digest auth improvements, and detection-type endpoints
- 39 tests green; PostgreSQL upsert idempotency confirmed by double-sync dedup test

## Self-Check: PASSED

All files verified present. All task commits verified in git log.

- FOUND: app/cameras/routes.py
- FOUND: app/cameras/schemas.py
- FOUND: app/isapi/client.py
- FOUND: tests/test_cameras.py
- FOUND: 01-03-SUMMARY.md
- FOUND: a996db7 (test: NVR connectivity tests RED)
- FOUND: 5aaf5aa (feat: NVR connectivity endpoint GREEN)
- FOUND: c32e7eb (test: camera sync tests RED)
- FOUND: b330771 (feat: camera sync endpoint GREEN)

---
*Phase: 01-foundation*
*Completed: 2026-03-10*
