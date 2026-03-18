---
phase: 02-isapi-core-operations
status: passed
verified_date: 2026-03-17
verified_by: Claude (Phase 08 retroverification)
requirements_count: 22
satisfied: 22
partial: 0
failed: 0
---

# Phase 02 Verification Report

Phase 02 implemented the complete ISAPI client and partition arm/disarm operations for the Hikvision NVR Partition Manager. The ISAPIClient class provides Digest-authenticated, TLS-tolerant HTTP access to Hikvision ISAPI endpoints with per-method retry on timeout. The disarm operation captures detection configuration snapshots from all 4 ISAPI detection endpoints, disables active detections via PUT, tracks multi-partition refcounts, and schedules auto-rearm jobs. The arm operation reverses this: decrements refcounts and restores original detection XML when the last partition arms. This retroverification confirms that all 22 requirements are fully satisfied. The test suite (32 tests across test_isapi_client.py, test_disarm.py, test_arm.py) passes green. All code citations below reference the live production files as of 2026-03-17.

## Summary Table

| ID | Requirement (brief) | Status | Evidence |
|----|---------------------|--------|----------|
| ISAPI-01 | HTTP Digest Authentication | SATISFIED | client.py:33; test_client_uses_digest_auth_and_no_tls_verify |
| ISAPI-02 | Connection and Read Timeouts | SATISFIED | client.py:37; test_client_timeout_settings |
| ISAPI-03 | Retry Once on Timeout | SATISFIED | client.py:47-50,62-68,85-88,103-114; 5 retry tests |
| ISAPI-04 | Accept Self-Signed TLS Certificates | SATISFIED | client.py:36; test_client_uses_digest_auth_and_no_tls_verify |
| ISAPI-05 | XML Response Parsing | SATISFIED | client.py:117-137; service.py:51-70; multiple tests |
| DARM-01 | POST disarm endpoint | SATISFIED | routes.py:61-73; test_disarm_success, test_disarm_idempotent |
| DARM-02 | NVR pre-check before disarm | SATISFIED | service.py:140-166; test_disarm_nvr_failure |
| DARM-03 | Read all 4 detection endpoints | SATISFIED | service.py:192-199; test_disarm_success |
| DARM-04 | Snapshot immutability | SATISFIED | service.py:206-222; test_disarm_snapshot_protection, test_disarm_camera_already_disarmed_by_other_partition |
| DARM-05 | Disable enabled detections via PUT | SATISFIED | service.py:227-230; test_disarm_success |
| DARM-06 | Refcount increment | SATISFIED | service.py:233-244; test_disarm_success |
| DARM-07 | Schedule auto-rearm | SATISFIED | service.py:272-273,295-296; test_disarm_calls_schedule_rearm_when_auto_rearm_minutes_set |
| DARM-08 | Audit log on disarm | SATISFIED | service.py:278-289; test_disarm_success |
| DARM-09 | Response fields | SATISFIED | service.py:298-303; test_disarm_success, test_disarm_camera_already_disarmed_by_other_partition |
| DARM-10 | Parallel ISAPI calls | SATISFIED (by inspection) | service.py:172,256; asyncio.Lock + asyncio.gather |
| ARM-01 | POST arm endpoint | SATISFIED | routes.py:75-87; test_arm_success_single_partition, test_arm_idempotent |
| ARM-02 | Refcount decrement | SATISFIED | service.py:388-390; test_arm_success_single_partition |
| ARM-03 | Restore detection config when refcount reaches 0 | SATISFIED | service.py:403-411; test_arm_success_single_partition |
| ARM-04 | Stay disarmed when refcount > 0 | SATISFIED | service.py:413-419; test_arm_multi_partition_stay_disarmed |
| ARM-05 | Cancel pending rearm job on arm | SATISFIED | service.py:318,430; test_arm_calls_cancel_rearm, test_arm_success_single_partition |
| ARM-06 | Audit log on arm | SATISFIED | service.py:434-443; test_arm_creates_audit_log_entry |
| ARM-07 | Response fields | SATISFIED | service.py:447-451; test_arm_success_single_partition, test_arm_restore_failure |

## ISAPI Requirements

### ISAPI-01 — HTTP Digest Authentication

The spec requires that all ISAPI calls use Digest authentication, not Basic. In `app/isapi/client.py`, ISAPIClient.__init__ at line 33 sets `self._auth = httpx.DigestAuth(username, password)`. This _auth instance is then included in the shared `_client_kwargs` dict at line 35 as `"auth": self._auth`. Every method that creates an `httpx.AsyncClient` passes `**self._client_kwargs`, ensuring all HTTP requests carry Digest credentials automatically. The test `test_client_uses_digest_auth_and_no_tls_verify` in test_isapi_client.py constructs an ISAPIClient and asserts `isinstance(client._auth, httpx.DigestAuth)` and that `client._client_kwargs["auth"]` is `client._auth`, confirming both the type and the wiring.

### ISAPI-02 — Connection and Read Timeouts

The spec requires a connect timeout of 5 seconds and a read timeout of 10 seconds. `app/isapi/client.py` line 37 sets `"timeout": httpx.Timeout(10.0, connect=5.0, read=10.0)` within `_client_kwargs`. The positional first argument `10.0` is the default timeout (required by httpx 0.28+), and the keyword arguments `connect=5.0` and `read=10.0` override the connect and read phases specifically. This was a key Phase 02 decision: httpx 0.28+ changed the Timeout API to require the positional default arg. The test `test_client_timeout_settings` constructs an ISAPIClient, retrieves `client._client_kwargs["timeout"]`, and asserts `.connect == 5.0` and `.read == 10.0`, directly verifying the configured values.

### ISAPI-03 — Retry Once on Timeout

The spec requires that each ISAPI call retries exactly once on timeout before propagating the exception; non-timeout errors must not be retried. The retry pattern is implemented inline (try/except catching `httpx.TimeoutException`) in all four request methods:

- `get_device_info` at client.py:47-50: the first GET is in a try block; catching `httpx.TimeoutException` triggers a second GET on line 50. If the second also times out, the exception propagates naturally.
- `get_camera_channels` at client.py:62-68: same pattern; first GET at 62, retry GET at 66-68.
- `get_detection_config` at client.py:85-88: first GET at 86, retry at 88.
- `put_detection_config` at client.py:103-114: first PUT at 104-108, retry PUT at 110-114.

In all methods, `resp.raise_for_status()` is called after the try/except block, meaning HTTP 4xx/5xx errors from the NVR are raised immediately without retry. Note: `get_device_info` and `get_camera_channels` received retry logic during Phase 07 (they were originally Phase 01 without retry); all four methods share the same inline pattern. Tests covering retry behavior: `test_get_detection_config_timeout_retries_once_then_raises`, `test_get_detection_config_first_timeout_second_success`, `test_put_detection_config_timeout_retries_once_then_raises`, `test_get_device_info_timeout_retries_once_then_raises`, `test_get_camera_channels_timeout_retries_once_then_raises`. Tests also verify non-timeout errors skip retry: `test_get_detection_config_non_timeout_error_raises_immediately`, `test_put_detection_config_non_timeout_error_raises_immediately`.

### ISAPI-04 — Accept Self-Signed TLS Certificates

The spec requires that TLS certificate verification be disabled so that NVRs with self-signed certificates are reachable. `app/isapi/client.py` line 36 sets `"verify": False` in `_client_kwargs` with the inline comment `# NVRs commonly use self-signed certs`. This key is shared with every `httpx.AsyncClient(**self._client_kwargs)` instantiation across all four request methods. The test `test_client_uses_digest_auth_and_no_tls_verify` is shared with ISAPI-01 and asserts `client._client_kwargs["verify"] is False`, confirming that verify is disabled at the client configuration level and not just for individual requests.

### ISAPI-05 — XML Response Parsing

The spec requires that ISAPI responses are parsed as XML, not JSON. This requirement is satisfied at two layers:

Layer 1 — ISAPIClient parsing: `app/isapi/client.py` defines `_parse_xml` at lines 117-120 and `_parse_channel_list` at lines 122-137, both using `xml.etree.ElementTree` (imported at line 6). `_parse_xml` strips XML namespace prefixes by splitting on `}` and returns a flat dict of child tag names to text values. `_parse_channel_list` iterates the tree looking for `VideoInputChannel` elements and extracts `id` and `name` sub-elements into channel dicts. The `get_detection_config` method returns the raw XML string (not parsed), as detection XML must be preserved in full for later PUT operations.

Layer 2 — service.py helpers: `app/partitions/service.py` defines `_is_enabled_in_xml` at lines 51-60 and `_disable_in_xml` at lines 63-70, both using `xml.etree.ElementTree` (imported at line 3). `_is_enabled_in_xml` parses the XML string, iterates all elements, and returns True if the first `enabled` element's text (case-normalized) is `"true"`. `_disable_in_xml` parses the XML, finds the `enabled` element, sets its text to `"false"`, and re-serializes the entire tree with `ET.tostring(root, encoding="unicode")` — preserving all other settings, namespaces stripped by libxml2.

Tests: `test_get_detection_config_success_returns_xml` in test_isapi_client.py confirms `get_detection_config` returns a string (not a dict). The full disarm integration tests (`test_disarm_success`, `test_disarm_snapshot_protection`) provide detection XML fixtures and verify that `put_detection_config` is called with modified XML, exercising `_is_enabled_in_xml` and `_disable_in_xml` in context.

## Disarm Operation

### DARM-01 — POST disarm endpoint

The spec requires a POST endpoint at `/api/partitions/{id}/disarm` that accepts a disarm request and returns a structured response. `app/partitions/routes.py` line 61 defines the route: `@router.post("/{partition_id}/disarm", response_model=APIResponse[DisarmResponse])`. The route function at lines 62-73 accepts `partition_id: uuid.UUID` as a path parameter and `body: DisarmRequest` as the request body. `DisarmRequest` schema requires `disarmed_by` (str) and accepts optional `reason` (str). The function delegates to `disarm_partition()` from service.py and wraps the result in `APIResponse(success=True, data=result)`. HTTPException and general exceptions are caught and returned as `APIResponse(success=False, error=...)` — maintaining a consistent envelope regardless of outcome. Test `test_disarm_success` fires a POST to this endpoint with a JSON body and verifies a 200 response with `success=True` and the expected `DisarmResponse` fields. Test `test_disarm_idempotent` fires the endpoint twice and verifies the second call returns success without re-snapshotting.

### DARM-02 — NVR pre-check before disarm

The spec requires that all NVRs hosting partition cameras are verified reachable before any disarm ISAPI work begins. `app/partitions/service.py` lines 140-166 implement this pre-check. After loading cameras (line 107), the code collects unique `nvr_id` values from camera records (line 134), queries all those NVRs from the database (lines 135-137), then iterates them at lines 141-166: for each NVR it decrypts the password, constructs an ISAPIClient, and calls `await client.get_device_info()`. On success (lines 146-148), the NVR's `status` is set to `"online"` and `last_seen_at` is updated (satisfying NVR-05 as a side effect). On any exception (lines 149-166), `state.state` is set to `"error"`, `state.error_detail` records the NVR IP and error message, a `disarm_failed` audit log entry is created and committed, and an HTTPException with status 400 is raised — aborting the disarm before any camera ISAPI GETs are attempted. Test `test_disarm_nvr_failure` uses a `FailingMockISAPIClient` that raises on `get_device_info` and asserts that `state.state == "error"` and `state.error_detail` contains the NVR address after the call returns an error response.

### DARM-03 — Read all 4 detection endpoints

The spec requires reading detection configuration from all 4 ISAPI detection endpoint types (MotionDetection, LineDetection, FieldDetection, shelteralarm). `app/partitions/service.py` defines `DETECTION_TYPES = ["MotionDetection", "LineDetection", "FieldDetection", "shelteralarm"]` at lines 43-48. Within `process_camera`, the loop at lines 192-199 iterates all four types: each `get_detection_config` call is wrapped in its own try/except (lines 193-199) so that a failure on one type (e.g., camera does not support that detection type) does not prevent attempting the others. Only responses that succeed add to `snapshot_data` dict (line 195); `found_any` tracks whether at least one GET succeeded. If `found_any` remains False after all four attempts (line 201-202), an exception is raised and the camera is added to the errors list. Partial success (some types fail) is allowed — only successfully fetched types are saved in the snapshot. Test `test_disarm_success` seeds a mock ISAPI client that returns XML for all four types and verifies all four are stored in `snapshot.snapshot_data` after the disarm call.

### DARM-04 — Snapshot immutability (do not overwrite existing snapshot)

This is the most nuanced requirement in Phase 02. The implementation uses two sequential checks within `process_camera` at `app/partitions/service.py` lines 206-222.

Query 1 (partition-scoped, line 181-186): before fetching any ISAPI data, the code checks whether THIS partition already has a `CameraDetectionSnapshot` row for this camera. If one is found, the entire snapshot creation block is skipped — `snapshot_data` is set directly from the existing snapshot (line 224), no ISAPI GETs are issued, and no new snapshot is written. This handles idempotent re-disarm: calling disarm a second time for the same partition does not overwrite the original armed-state snapshot.

Query 2 (camera-scoped ANY, lines 208-214): if no partition-scoped snapshot exists, the code proceeds to fetch live ISAPI data, then — before persisting — queries for any snapshot for this camera from ANY partition (no `partition_id` filter, line 208-210). If `existing_any` is found (line 212), `final_snapshot_data = existing_any.snapshot_data` (line 214): the freshly-fetched live ISAPI data is discarded in favor of the existing snapshot's data. This preserves the original armed state when a second partition disarms a camera already disarmed by a different partition. The new snapshot for THIS partition is then created with `final_snapshot_data` (lines 216-221) so that when this partition arms, it restores from that same baseline. Line 222 also updates `snapshot_data` to `final_snapshot_data` for the subsequent PUT calls, so only detection types that were originally enabled are disabled.

Tests: `test_disarm_snapshot_protection` pre-seeds a `CameraDetectionSnapshot` for the SAME partition with custom `snapshot_data`, calls disarm again, and verifies the snapshot row is unchanged after the second call. `test_disarm_camera_already_disarmed_by_other_partition` seeds a snapshot from a DIFFERENT partition, calls disarm for the current partition, and verifies the current partition's snapshot uses the seeded data (not fresh ISAPI data), and that both partition IDs appear in the refcount.

### DARM-05 — Disable enabled detections via PUT

The spec requires that each detection type found enabled in the snapshot is disabled via PUT, while already-disabled types are silently skipped. `app/partitions/service.py` lines 227-230 implement this: `for d_type, xml in snapshot_data.items(): if _is_enabled_in_xml(xml):`. Only if `_is_enabled_in_xml(xml)` returns True (i.e., the `enabled` element in the snapshot XML is `"true"`) does the code call `_disable_in_xml(xml)` to produce new XML with `enabled` set to `"false"`, then PUT that new XML back to the NVR via `client.put_detection_config(camera.channel_no, d_type, new_xml)`. Detection types that have `enabled=false` in the snapshot (already disabled at armed time) are skipped entirely, producing no PUT call. Test `test_disarm_success` seeds a mock ISAPI client returning XML with `<enabled>true</enabled>` and asserts that `put_detection_config` is called for each of the four detection types, verifying the gate logic fires correctly for enabled detections.

### DARM-06 — Refcount increment

The spec requires that each disarm increments a per-camera reference count tracking which partitions have disarmed a given camera. `app/partitions/service.py` lines 233-244 implement this within `process_camera`, protected by `db_lock`. The code fetches or creates a `CameraDisarmRefcount` row (line 234-239), then at line 241 checks `if partition_id not in refcount.disarmed_by_partitions` before appending — making the increment idempotent. Lines 242-244 build a new list, append `partition_id`, and assign it back to trigger SQLAlchemy dirty-tracking for the PostgreSQL array column. Lines 247-250 determine whether to increment `cameras_disarmed` or `cameras_kept_disarmed_by_other_partition` based on whether the refcount after append is greater than 1. Test `test_disarm_success` queries the `CameraDisarmRefcount` table after disarm and asserts `part.id in refcount.disarmed_by_partitions`. Test `test_disarm_camera_already_disarmed_by_other_partition` calls disarm from two different partitions on the same camera and verifies both partition IDs are present in the array.

### DARM-07 — Schedule auto-rearm

The spec requires that after a successful disarm, if the partition has `auto_rearm_minutes` configured, a future rearm job is scheduled. `app/partitions/service.py` lines 271-275 handle this: if `partition.auto_rearm_minutes` is set, `state.scheduled_rearm_at` is computed as `state.last_changed_at + timedelta(minutes=partition.auto_rearm_minutes)` (line 273); otherwise it is set to None (line 275). After committing the state to the database (line 292), lines 295-296 check `if state.scheduled_rearm_at is not None: await schedule_rearm(partition_id, state.scheduled_rearm_at)` — calling the APScheduler job creator conditionally. Test `test_disarm_calls_schedule_rearm_when_auto_rearm_minutes_set` seeds a partition with `auto_rearm_minutes=30`, patches `schedule_rearm` with a mock, calls disarm, and asserts the mock was called exactly once with the correct `partition_id` argument.

### DARM-08 — Audit log on disarm

The spec requires that every disarm operation (successful or failed) creates an audit log entry. `app/partitions/service.py` lines 278-289 create a `PartitionAuditLog` with `action="disarm"`, `partition_id=partition_id`, `performed_by=disarmed_by`, and `audit_metadata` containing `reason`, `cameras_disarmed`, `cameras_kept_disarmed_by_other_partition`, and `errors_count`. The failure path at lines 155-162 also creates a `PartitionAuditLog` with `action="disarm_failed"` when an NVR pre-check fails, ensuring the audit trail is complete even for rejected operations. Test `test_disarm_success` queries the `PartitionAuditLog` table after the call and asserts `audits[0].action == "disarm"` and `audits[0].performed_by == "test-user"`. Test `test_disarm_nvr_failure` verifies that a `disarm_failed` audit log entry is created when the NVR pre-check fails.

### DARM-09 — Response fields

The spec requires the disarm response to include: `cameras_disarmed`, `cameras_kept_disarmed_by_other_partition`, `scheduled_rearm_at`, and `errors`. `app/partitions/service.py` lines 298-303 construct and return `DisarmResponse(cameras_disarmed=cameras_disarmed, cameras_kept_disarmed_by_other_partition=cameras_kept_disarmed_by_other_partition, scheduled_rearm_at=state.scheduled_rearm_at, errors=errors)`. All four fields are always present in the response (errors defaults to an empty list when none occur). Test `test_disarm_success` checks all four fields in the response data. Test `test_disarm_camera_already_disarmed_by_other_partition` verifies `cameras_disarmed=1` and `cameras_kept_disarmed_by_other_partition=1` when one camera is freshly disarmed by this partition and one is already held by another. Test `test_disarm_partial_failure` verifies the `errors` list is populated with per-camera error details when an ISAPI call fails.

### DARM-10 — Parallel ISAPI calls (SATISFIED BY INSPECTION)

**Status: SATISFIED (by inspection) — structural/async behavior; no automated concurrency test.**

This requirement specifies that per-camera ISAPI calls during disarm should execute in parallel rather than sequentially. The implementation satisfies this through two complementary mechanisms in `app/partitions/service.py`:

First, `db_lock = asyncio.Lock()` at line 172 is created before the parallel execution begins. All database write operations inside `process_camera` that mutate shared session state (snapshot creation at line 205, refcount update at line 233) are wrapped in `async with db_lock:` blocks. This serializes DB writes while allowing ISAPI HTTP calls — which do not acquire the lock — to run concurrently.

Second, line 256 executes `await asyncio.gather(*(process_camera(c) for c in cameras))` — a generator expression that spawns one coroutine per camera and passes all of them to `asyncio.gather`. `asyncio.gather` runs all coroutines concurrently within the event loop: the ISAPI GET and PUT calls for different cameras interleave at every `await` point rather than being awaited sequentially. The same pattern appears in `arm_partition` at line 424.

STATE.md records the design rationale: "asyncio.Lock used in disarm_partition loop to prevent concurrent DB writes on the same AsyncSession from causing SAWarnings during parallel ISAPI calls." This is a structural behavior verifiable by code inspection; automated concurrency tests would require timing control and are out of scope for Phase 02 verification.

## Arm Operation

### ARM-01 — POST arm endpoint

The spec requires a POST endpoint at `/api/partitions/{id}/arm` that accepts an arm request and returns a structured response. `app/partitions/routes.py` line 75 defines the route: `@router.post("/{partition_id}/arm", response_model=APIResponse[ArmResponse])`. The route function at lines 76-87 accepts `partition_id: uuid.UUID` and `body: ArmRequest`. `ArmRequest` schema requires `armed_by` (str). The function delegates to `arm_partition()` from service.py and wraps the result in `APIResponse(success=True, data=result)`. The arm operation proceeds from any non-armed state (disarmed, partial, error) and is idempotent from the armed state (returns `cameras_restored=0, cameras_kept_disarmed=0` without error). Tests: `test_arm_success_single_partition` exercises the standard arm path; `test_arm_idempotent` verifies no-op behavior from an already-armed state; `test_arm_from_partial_state_succeeds` and `test_arm_from_error_state_succeeds` verify the endpoint accepts and processes arms from non-standard states.

### ARM-02 — Refcount decrement

The spec requires that arming decrements the per-camera partition refcount for the arming partition. `app/partitions/service.py` lines 384-390 implement this inside `process_camera`. At line 384, a guard checks `if not refcount or partition_id not in refcount.disarmed_by_partitions` — if this partition never disarmed the camera, it is skipped entirely (early return at line 386). Lines 388-390 build `new_partitions = list(refcount.disarmed_by_partitions)`, call `new_partitions.remove(partition_id)` (list.remove removes the first occurrence), and assign `refcount.disarmed_by_partitions = new_partitions` to trigger dirty-tracking. Line 392 computes `remaining_count = len(new_partitions)` which drives the restore-vs-stay-disarmed decision. Test `test_arm_success_single_partition` asserts `len(refcount.disarmed_by_partitions) == 0` after a single-partition arm. Test `test_arm_multi_partition_stay_disarmed` seeds two partitions in the refcount, arms partition 1 only, and asserts only partition 2's ID remains in the array.

### ARM-03 — Restore detection config when refcount reaches 0

The spec requires that when the last partition arms a camera (refcount reaches 0), the original detection configuration is restored via PUT. `app/partitions/service.py` lines 403-412 implement this. When `remaining_count == 0`, the code iterates `snapshot.snapshot_data.items()` and for each `(d_type, xml)` calls `await client.put_detection_config(camera.channel_no, d_type, xml)` — sending the ORIGINAL armed-state XML (not the disabled version that was PUT during disarm). After all PUTs succeed, `await db.delete(snapshot)` at line 410 removes the `CameraDetectionSnapshot` row. `cameras_restored` is incremented at line 412. Test `test_arm_success_single_partition` verifies `cameras_restored == 1`, asserts that `put_detection_config` was called for each detection type in the snapshot, and queries the database to confirm no snapshot row remains after the arm operation.

### ARM-04 — Stay disarmed when refcount > 0

The spec requires that when other partitions still hold a disarm refcount, arming one partition does not restore detection (the camera stays disarmed). The else branch at `app/partitions/service.py` lines 413-419 handles this: when `remaining_count > 0`, no `put_detection_config` calls are made. If a `CameraDetectionSnapshot` exists for THIS partition, it is deleted (lines 415-417) since this partition is no longer a disarm holder — but the camera's detection remains disabled because the refcount is nonzero. `cameras_kept_disarmed` is incremented at line 419. Test `test_arm_multi_partition_stay_disarmed` seeds two partitions disarming the same camera, arms only partition 1, and asserts `cameras_kept_disarmed == 1` and that `put_detection_config` was not called (detection left disabled for partition 2's benefit).

### ARM-05 — Cancel pending rearm job on arm

The spec requires that any scheduled auto-rearm job be cancelled when the partition is manually armed. `app/partitions/service.py` line 318 calls `await cancel_rearm(partition_id)` UNCONDITIONALLY — positioned before any idempotency check or database reads. This means the cancel fires even when arming an already-armed partition or when arming an error-state partition. The `cancel_rearm` implementation (in `app/jobs/auto_rearm`) catches `ScheduleLookupError` from APScheduler 4.x if no scheduled job exists, so calling cancel on a partition that never had auto-rearm configured is safe. After the arm operation completes and state is updated, line 430 sets `state.scheduled_rearm_at = None` — clearing the scheduled time in the database as well. STATE.md records the decision: "cancel_rearm catches ScheduleLookupError (APScheduler 4.x) — not JobLookupError." Test `test_arm_calls_cancel_rearm` patches `cancel_rearm` with a mock and asserts it was called exactly once with the correct `partition_id`. Test `test_arm_success_single_partition` asserts `state.scheduled_rearm_at is None` after arm completion.

### ARM-06 — Audit log on arm

The spec requires that every arm operation creates an audit log entry. `app/partitions/service.py` lines 434-443 create a `PartitionAuditLog` with `action="arm"`, `partition_id=partition_id`, `performed_by=armed_by` (from `ArmRequest.armed_by`), and `audit_metadata` containing `cameras_restored`, `cameras_kept_disarmed`, and `errors_count`. The audit entry is added before `await db.commit()` at line 446, ensuring it is always committed atomically with the state update. Test `test_arm_creates_audit_log_entry` queries the `PartitionAuditLog` table after arm and asserts `audit.action == "arm"` and `audit.performed_by == "test-user"`.

### ARM-07 — Response fields

The spec requires the arm response to include: `cameras_restored`, `cameras_kept_disarmed`, and `errors`. `app/partitions/service.py` lines 448-451 construct and return `ArmResponse(cameras_restored=cameras_restored, cameras_kept_disarmed=cameras_kept_disarmed, errors=errors)`. All three fields are always present (errors defaults to empty list). Test `test_arm_success_single_partition` checks `cameras_restored == 1`, `cameras_kept_disarmed == 0`, and `errors == []`. Test `test_arm_restore_failure` seeds a scenario where `put_detection_config` raises during restore and asserts the `errors` list is populated with a `PartitionError` containing the camera ID and error message.
