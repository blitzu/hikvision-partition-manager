---
phase: 01-foundation
plan: "02"
subsystem: api
tags: [fastapi, pydantic, sqlalchemy, fernet, encryption, zoneinfo, pytest-asyncio]

# Dependency graph
requires:
  - phase: 01-foundation/01-01
    provides: "Location + NVRDevice ORM models, get_db dependency, encrypt_password helper, APIResponse[T] envelope, conftest.py fixtures"
provides:
  - POST /api/locations — create location with timezone validation (ZoneInfo, 422 on invalid)
  - GET /api/locations — list all locations ordered by name
  - POST /api/locations/{id}/nvrs — create NVR with Fernet-encrypted password, 404->success=false
  - GET /api/locations/{id}/nvrs — list NVRs for location
  - LocationCreate schema with @field_validator for timezone (ZoneInfoNotFoundError -> 422)
  - LocationRead schema (id, name, timezone, created_at)
  - NVRCreate schema (accepts plaintext password for input only)
  - NVRRead schema (no password or password_encrypted field — structural exclusion)
  - 13 passing tests across test_locations.py and test_nvrs.py
affects: [03-cameras-sync, 04-partitions-arming, 05-scheduler, 06-admin-ui]

# Tech tracking
tech-stack:
  added: []  # no new dependencies; all libraries from Plan 01-01
  patterns:
    - zoneinfo.ZoneInfo in Pydantic @field_validator for IANA timezone validation
    - Structural password exclusion via omission — NVRRead schema has no password field
    - encrypt_password() called before any DB write — plaintext never touches storage layer
    - APIRouter prefix pattern: locations router at /api/locations, nvrs router at /api

key-files:
  created:
    - app/locations/schemas.py
    - app/locations/routes.py
    - app/nvrs/schemas.py
    - app/nvrs/routes.py
    - tests/test_locations.py
    - tests/test_nvrs.py
  modified:
    - app/main.py (added include_router for locations and nvrs)

key-decisions:
  - "NVRRead schema uses structural exclusion — password field is absent from schema, not excluded via field flags"
  - "NVR router prefix is /api (not /api/locations) to naturally support /api/locations/{id}/nvrs path shape"
  - "encrypt_password(body.password) called before NVRDevice ORM object instantiation — plaintext never touches any model attribute"

patterns-established:
  - "Pattern: Structural field exclusion — omit sensitive fields from response schema entirely rather than using exclude= flags"
  - "Pattern: ZoneInfo validator — field_validator on timezone str raises ValueError for ZoneInfoNotFoundError, FastAPI converts to 422"
  - "Pattern: Unknown FK returns APIResponse(success=False, error='X not found') — not HTTP 404 — consistent with envelope contract"

requirements-completed: [NVR-01, NVR-02, NVR-06]

# Metrics
duration: 8min
completed: 2026-03-10
---

# Phase 1 Plan 02: Location and NVR CRUD Summary

**POST/GET /api/locations and POST/GET /api/locations/{id}/nvrs with Fernet password encryption and structural NVRRead schema that makes password leakage impossible at the serialization layer**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-03-10T13:21:28Z
- **Completed:** 2026-03-10T13:28:00Z
- **Tasks:** 2
- **Files modified:** 7 (6 created, 1 modified)

## Accomplishments

- Location schemas with IANA timezone validation via `ZoneInfo` — invalid timezone raises 422 before any DB call
- NVR schemas implementing structural password exclusion: `NVRRead` has no `password` or `password_encrypted` field, making serialization-layer leakage architecturally impossible
- Fernet encryption enforced before any `NVRDevice` attribute is set — plaintext never stored
- All unknown-location cases return `APIResponse(success=False, error="Location not found")` inside the 200 envelope, consistent with the established response contract
- 28/28 tests passing (15 prior + 6 location + 7 NVR)

## Task Commits

Each task was committed atomically (TDD: RED then GREEN):

1. **Task 1 RED: Failing location tests** - `092abb6` (test)
2. **Task 1 GREEN: Location schemas and CRUD routes** - `a25538d` (feat)
3. **Task 2 RED: Failing NVR tests** - `c3e7b98` (test)
4. **Task 2 GREEN: NVR schemas and CRUD routes** - `c423f77` (feat)

_TDD pattern: each task has test commit (failing) + feat commit (passing)_

## Files Created/Modified

- `app/locations/schemas.py` - LocationCreate with ZoneInfo field_validator, LocationRead with from_attributes
- `app/locations/routes.py` - POST/GET /api/locations using APIResponse[LocationRead] envelope
- `app/nvrs/schemas.py` - NVRCreate (accepts password), NVRRead (no password fields)
- `app/nvrs/routes.py` - POST/GET /api/locations/{id}/nvrs with encrypt_password before DB write
- `app/main.py` - Added include_router for both locations and nvrs routers
- `tests/test_locations.py` - 6 tests: create, invalid timezone, missing name, list empty, list after create, field set check
- `tests/test_nvrs.py` - 7 tests: create success, DB encryption check, password absent from response text, no password key in response, list NVRs, location linkage, unknown location

## Decisions Made

- **NVRRead structural exclusion:** NVR password protection is enforced by not defining any password-related field on `NVRRead`. This is safer than `exclude=True` flags — Pydantic `model_validate(orm_obj)` will only include fields declared on the schema, so the encrypted value is silently ignored even though it exists on the ORM model.
- **NVR router prefix `/api`:** The NVR router uses prefix `/api` (not `/api/locations`) so that the route path `/locations/{location_id}/nvrs` naturally matches the full URL `/api/locations/{id}/nvrs`. The locations router correctly owns the `/api/locations` prefix.
- **encrypt before instantiate:** `encrypt_password(body.password)` is called and stored in a local variable `encrypted` before `NVRDevice(...)` is constructed. This ensures plaintext never becomes an ORM attribute.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All 4 foundational API endpoints available for Plan 03 (camera sync)
- NVR records contain `ip_address`, `port`, `username`, `password_encrypted` — Plan 03 can call `decrypt_password()` to authenticate against ISAPI
- `conftest.py` `client` + `db_session` fixtures continue to work for all new test files
- Both routers registered in `app/main.py` — Plan 03 just adds a cameras router with same pattern

## Self-Check: PASSED
