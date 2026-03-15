# Plan Summary - Phase 02 Plan 03

## Status
- [x] Task 1: Implement arm_partition service and route
- [x] Integration tests in `tests/test_arm.py` passed.
- [x] Snapshot immutability across multiple partitions implemented and verified.
- [x] No regressions in existing test suite.

## Changes

### app/partitions/service.py
- Implemented `arm_partition` async function.
- Features:
    - Idempotency: graceful no-op if partition is already armed.
    - Refcount decrement: removes partition ID from the camera's `disarmed_by_partitions` list.
    - Conditional restoration: only calls ISAPI `put_detection_config` if the camera's refcount reached 0.
    - Snapshot deletion: removes the per-partition camera snapshot after arming (whether restored or not, to keep DB clean).
    - Parallel execution: uses `asyncio.gather` with `db_lock` for concurrent NVR/DB operations.
    - Audit logging: records "arm" actions with metadata.
    - State transition: sets partition state to "armed" and clears `scheduled_rearm_at` (ARM-05).
- Updated `disarm_partition`:
    - Implemented **Snapshot Immutability (DARM-04)**: when a camera is disarmed, if a snapshot already exists for that camera (from another partition), it COPIES that snapshot instead of fetching from ISAPI. This ensures the *original* armed state is preserved even if the camera is already disarmed.

### app/partitions/routes.py
- Added `POST /api/partitions/{partition_id}/arm` endpoint.
- Returns `APIResponse[ArmResponse]`.

### tests/test_arm.py
- Integration tests covering:
    - Single-partition arm (restores detection).
    - Multi-partition arm (refcount logic: camera stays disarmed).
    - Idempotency.
    - Restore failure handling (snapshot not deleted on failure).

## Verification Results
- `pytest tests/test_arm.py -v` - 4/4 passed.
- `pytest tests/ -v` - 58/58 passed.
