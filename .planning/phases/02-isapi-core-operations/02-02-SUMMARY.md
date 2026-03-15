# Plan Summary - Phase 02 Plan 02

## Status
- [x] Task 1: Define disarm/arm Pydantic schemas
- [x] Task 2: Implement disarm_partition service and route
- [x] All integration tests in `tests/test_disarm.py` passed.
- [x] No regressions in existing test suite.

## Changes

### app/partitions/schemas.py
- Created with `DisarmRequest`, `DisarmResponse`, `ArmRequest`, `ArmResponse`, and `PartitionError` Pydantic models.
- These models define the contract for the disarm/arm API endpoints.

### app/partitions/service.py
- Implemented `disarm_partition` async function.
- Features:
    - NVR pre-check: verifies connectivity to all involved NVRs before modifying any camera state.
    - Idempotency: graceful no-op if partition is already disarmed.
    - Snapshot capture: GETs detection config (Motion, Line, Field, Shelter) and saves to `CameraDetectionSnapshot` (prevents overwriting existing snapshots).
    - Parallel execution: uses `asyncio.gather` with a `db_lock` to safely perform ISAPI calls in parallel while maintaining DB integrity.
    - Refcounting: updates `CameraDisarmRefcount` to track which partitions have disarmed a camera.
    - Audit logging: records "disarm" or "disarm_failed" actions.
    - Automatic state transitions: "armed" -> "disarmed" (or "partial"/"error").
    - Scheduled rearm: sets `scheduled_rearm_at` if `auto_rearm_minutes` is configured.

### app/partitions/routes.py
- Created with `POST /api/partitions/{partition_id}/disarm` endpoint.
- Returns `APIResponse[DisarmResponse]`.

### app/main.py
- Registered `partitions_router`.

### tests/test_disarm.py
- Comprehensive integration tests covering:
    - Success path (full disarm).
    - Idempotency.
    - Snapshot protection (do not overwrite).
    - NVR pre-check failure.
    - Partial failure (one camera fails, state becomes "partial").

### tests/mocks.py
- Updated `MockISAPIClient.__init__` to accept `*args, **kwargs` to match the real client's signature.

## Verification Results
- `pytest tests/test_disarm.py -v` - 5/5 passed.
- `pytest tests/ -v` - 54/54 passed.
