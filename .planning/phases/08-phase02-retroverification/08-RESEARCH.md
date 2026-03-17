# Phase 8: Phase 02 Retroverification - Research

**Researched:** 2026-03-17
**Domain:** Verification audit of ISAPI client, disarm/arm service logic
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Gap Handling**
- If the verifier finds a real code gap: fix it in Phase 08 if it's small (< 1 day). If the gap is structural or large, defer to a new gap-closure phase rather than expanding Phase 08's scope.
- Before spawning the full verifier, pre-check the DARM/ARM service layer — read `app/partitions/service.py` to confirm `disarm_partition` and `arm_partition` functions exist and have the expected structure.
- Treat Phase 08 as a real audit (not a formality) — Phase 02 was complex and edge case gaps are possible (especially around DARM-04 snapshot immutability, DARM-10 parallelism, ARM-03 conditional restore).

**Verification File Placement**
- `02-VERIFICATION.md` must be written to `.planning/phases/02-isapi-core-operations/` — not Phase 08's directory.
- After verification passes, update REQUIREMENTS.md traceability to mark all ISAPI-01..05 and DARM-01..10 and ARM-01..07 rows as `Complete` (currently showing as `Pending` or `Phase 8 (gap)`).

**Evidence Standard**
- Both code AND tests required for each requirement to be `SATISFIED`. A requirement with code but no corresponding test gets a warning/partial.
- Exception for structural behaviors (e.g., DARM-10 parallelism, INFRA-06 graceful shutdown): code inspection is acceptable evidence. Document with: "asyncio.gather() at [file:line] — parallelism confirmed by inspection."
- Report format: Full narrative per requirement — not just a status badge. Each satisfied requirement gets a paragraph explaining how the implementation satisfies the spec, including file path and function name.
- Scope: Re-verify all 22 requirements fresh. Do not skip ISAPI-01..05 because they're already checked in REQUIREMENTS.md. Phase 08 is a clean audit of Phase 02's scope.

### Claude's Discretion
- How to structure the verification report sections (e.g., group by ISAPI/DARM/ARM or go requirement-by-requirement)
- Whether to include a summary table at the top in addition to full narratives
- How to handle requirements that are partially tested (warn vs fail)

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ISAPI-01 | All ISAPI calls use HTTP Digest Authentication (not Basic) | `ISAPIClient.__init__` sets `self._auth = httpx.DigestAuth(...)` at `app/isapi/client.py:33`; `test_client_uses_digest_auth_and_no_tls_verify` asserts `isinstance(isapi_client._auth, httpx.DigestAuth)` |
| ISAPI-02 | Connection timeout: 5 seconds; read timeout: 10 seconds | `httpx.Timeout(10.0, connect=5.0, read=10.0)` at `app/isapi/client.py:37`; `test_client_timeout_settings` asserts `.connect == 5.0` and `.read == 10.0` |
| ISAPI-03 | On timeout, system retries once before marking camera/NVR as error | Inline try/except pattern in `get_detection_config`, `put_detection_config`, `get_device_info`, `get_camera_channels`; 7 tests in `test_isapi_client.py` cover retry and no-retry paths |
| ISAPI-04 | System accepts self-signed TLS certificates from NVRs | `"verify": False` in `_client_kwargs` at `app/isapi/client.py:36`; `test_client_uses_digest_auth_and_no_tls_verify` asserts `_client_kwargs["verify"] is False` |
| ISAPI-05 | System parses XML responses (not JSON) from ISAPI endpoints | `_parse_xml` and `_parse_channel_list` use `xml.etree.ElementTree`; `get_detection_config` returns raw XML string; `_is_enabled_in_xml` and `_disable_in_xml` in `service.py` parse/manipulate XML |
| DARM-01 | External VMS can POST disarm with disarmed_by and optional reason | `POST /api/partitions/{id}/disarm` at `app/partitions/routes.py:61`; `DisarmRequest` schema accepts `disarmed_by` and `reason` |
| DARM-02 | Before disarming, system checks connectivity of all involved NVRs; on failure, sets state=error and returns error | NVR pre-check loop at `service.py:141-166` calls `get_device_info()`, sets `state.state = "error"` on exception; `test_disarm_nvr_failure` verifies error state and DB update |
| DARM-03 | For each camera, system reads current detection config from all 4 ISAPI endpoints; saves only endpoints returning HTTP 200 | Loop over `DETECTION_TYPES` at `service.py:192-199` with try/except — only successful GETs added to `snapshot_data`; `found_any` tracks success |
| DARM-04 | If a camera already has a snapshot, system does NOT overwrite the existing snapshot | Code at `service.py:206-222` queries `CameraDetectionSnapshot` for any existing snapshot; copies `existing_any.snapshot_data` if found; `test_disarm_snapshot_protection` and `test_disarm_camera_already_disarmed_by_other_partition` verify this |
| DARM-05 | System disables all detection types that were enabled=true in the snapshot via PUT ISAPI, preserving all other settings | `_disable_in_xml` sets `<enabled>false</enabled>` while re-serializing full XML tree; `_is_enabled_in_xml` gates the PUT call; `test_disarm_success` verifies PUT path executes |
| DARM-06 | System adds partition_id to camera's disarmed_by_partitions array (refcount increment) | Code at `service.py:233-244` appends `partition_id` to `CameraDisarmRefcount.disarmed_by_partitions`; `test_disarm_success` asserts `part.id in refcount.disarmed_by_partitions` |
| DARM-07 | If auto_rearm_minutes is set, system schedules a rearm job at the calculated time | `service.py:272-273` sets `scheduled_rearm_at`; `service.py:295-296` calls `await schedule_rearm(partition_id, ...)` when value is set; `test_disarm_calls_schedule_rearm_when_auto_rearm_minutes_set` verifies the call |
| DARM-08 | System appends audit log entry for disarm action | `PartitionAuditLog(action="disarm", ...)` added at `service.py:278-289`; `test_disarm_success` asserts `audits[0].action == "disarm"` |
| DARM-09 | Response includes cameras_disarmed count, cameras_kept_disarmed_by_other_partition count, scheduled_rearm_at, errors list | `DisarmResponse` returned with all four fields; `test_disarm_camera_already_disarmed_by_other_partition` verifies counter split |
| DARM-10 | ISAPI calls to cameras on the same NVR are executed in parallel, not sequentially | `asyncio.gather(*(process_camera(c) for c in cameras))` at `service.py:256`; parallelism confirmed by code inspection (structural behavior) |
| ARM-01 | External VMS can POST arm with armed_by | `POST /api/partitions/{id}/arm` at `routes.py:75`; `ArmRequest` schema accepts `armed_by`; idempotency path confirmed by `test_arm_idempotent` |
| ARM-02 | System removes this partition_id from each camera's disarmed_by_partitions array (refcount decrement) | `new_partitions.remove(partition_id)` at `service.py:389-390`; `test_arm_success_single_partition` asserts `len(refcount.disarmed_by_partitions) == 0` |
| ARM-03 | For cameras where refcount reaches 0: system restores detection config from snapshot via PUT ISAPI, then deletes snapshot record | `if remaining_count == 0` block at `service.py:403-411` calls `put_detection_config` then `db.delete(snapshot)`; `test_arm_success_single_partition` verifies snapshot deleted and `cameras_restored == 1` |
| ARM-04 | For cameras where refcount > 0: system logs that camera stays disarmed, does NOT restore detection | `else` block at `service.py:413-419` deletes snapshot but skips PUT; `test_arm_multi_partition_stay_disarmed` verifies `cameras_kept_disarmed == 1` |
| ARM-05 | System cancels any pending scheduled rearm job for this partition | `cancel_rearm(partition_id)` called unconditionally at `service.py:318` before any DB writes; `test_arm_calls_cancel_rearm` verifies the call; state cleared at `service.py:430` |
| ARM-06 | System appends audit log entry for arm action | `PartitionAuditLog(action="arm", ...)` added at `service.py:434-443`; `test_arm_creates_audit_log_entry` asserts `audit.performed_by == "test-user"` |
| ARM-07 | Response includes cameras_restored count, cameras_kept_disarmed count, errors list | `ArmResponse(cameras_restored=..., cameras_kept_disarmed=..., errors=errors)` returned at `service.py:447-451`; `test_arm_restore_failure` verifies errors list populated |
</phase_requirements>

---

## Summary

Phase 8 is a pure audit phase: produce `02-VERIFICATION.md` by formally verifying all 22 requirements from Phase 02 (ISAPI-01..05, DARM-01..10, ARM-01..07) with implementation evidence. No new code is expected unless the audit reveals a real gap.

The implementation is complete and the tests are green. All three primary source files have been read (`app/isapi/client.py`, `app/partitions/service.py`, `app/partitions/routes.py`). The 32 tests across `test_isapi_client.py`, `test_disarm.py`, and `test_arm.py` provide direct test coverage for every requirement except DARM-10, which is a structural behavior satisfied by code inspection. The existing `02-VALIDATION.md` maps each test to its requirement, which serves as a useful cross-reference during the audit.

Two requirements warrant extra scrutiny: DARM-04 (snapshot immutability) has a subtlety — the code copies from any existing snapshot for *any partition*, not just the same partition. This preserves original armed state across multi-partition disarm scenarios, and the test `test_disarm_camera_already_disarmed_by_other_partition` exercises exactly this path. DARM-10 (parallelism) is a structural claim backed by `asyncio.gather()` at `service.py:256` but has no dedicated concurrency test — this requires code-inspection evidence in the report per the locked decision.

**Primary recommendation:** Execute the audit, write the verification narrative grouped by ISAPI / DARM / ARM with a summary table at the top, then update REQUIREMENTS.md traceability rows from Pending to Complete.

---

## Architecture Patterns

### Verification Report Structure

The planner should produce `02-VERIFICATION.md` with the following structure:

```
.planning/phases/02-isapi-core-operations/02-VERIFICATION.md

├── Frontmatter (phase, status, date)
├── Summary table (ID | Status | Evidence type)
├── ## ISAPI Requirements (ISAPI-01..05)
│   └── Per requirement: narrative paragraph + file:line + test name
├── ## Disarm Operation (DARM-01..10)
│   └── Per requirement: narrative paragraph + file:line + test name
└── ## Arm Operation (ARM-01..07)
    └── Per requirement: narrative paragraph + file:line + test name
```

### Evidence Standard Per Requirement

Two tiers, per locked decisions:

| Evidence Tier | When | Format |
|---------------|------|--------|
| Code + Test (SATISFIED) | All requirements except structural behaviors | Narrative + `file:line` + `pytest test_name` passing |
| Code Inspection (SATISFIED by inspection) | Structural/async behaviors (DARM-10, parallelism) | Narrative + `file:line` + inspection rationale |

### Partial/Warning Handling

A requirement with code but no dedicated test gets status `PARTIAL` with a warning. Based on the audit findings, no requirement is in this state — all 22 have either dedicated tests or explicit code-inspection justification.

---

## Requirement-by-Requirement Evidence Map

This is the definitive research output for the planner. Every row specifies what the plan task must document.

### ISAPI Group

| ID | Status | Code Location | Test(s) | Notes |
|----|--------|---------------|---------|-------|
| ISAPI-01 | SATISFIED | `client.py:33` — `httpx.DigestAuth(username, password)` | `test_client_uses_digest_auth_and_no_tls_verify` | DigestAuth instance stored and passed via `_client_kwargs["auth"]` |
| ISAPI-02 | SATISFIED | `client.py:37` — `httpx.Timeout(10.0, connect=5.0, read=10.0)` | `test_client_timeout_settings` | httpx.Timeout positional-first syntax required in 0.28+ (Phase 02 decision) |
| ISAPI-03 | SATISFIED | `client.py:46-51`, `62-69`, `84-90`, `105-115` — inline try/except retry on `TimeoutException` | `test_get_detection_config_timeout_retries_once_then_raises`, `test_get_detection_config_first_timeout_second_success`, `test_put_detection_config_timeout_retries_once_then_raises`, `test_get_device_info_timeout_retries_once_then_raises`, `test_get_camera_channels_timeout_retries_once_then_raises`, `test_*_non_timeout_error_raises_immediately` | All 4 methods have retry. Non-timeout errors (4xx/5xx) pass through `raise_for_status()` without retry |
| ISAPI-04 | SATISFIED | `client.py:36` — `"verify": False` | `test_client_uses_digest_auth_and_no_tls_verify` (asserts `_client_kwargs["verify"] is False`) | Shared with ISAPI-01 test |
| ISAPI-05 | SATISFIED | `client.py:117-136` — `_parse_xml`, `_parse_channel_list` using `xml.etree.ElementTree`; `service.py:51-70` — `_is_enabled_in_xml`, `_disable_in_xml` | `test_get_detection_config_success_returns_xml`, `test_detection_url_pattern[*]`, full disarm/arm integration tests | XML parsed via stdlib ET; detection config GET returns raw XML string; PUT sends modified XML |

### DARM Group

| ID | Status | Code Location | Test(s) | Notes |
|----|--------|---------------|---------|-------|
| DARM-01 | SATISFIED | `routes.py:61-73` — `POST /{partition_id}/disarm`; `DisarmRequest` schema | `test_disarm_success`, `test_disarm_idempotent` | Endpoint accepts `disarmed_by` (required) and `reason` (optional) |
| DARM-02 | SATISFIED | `service.py:140-166` — NVR pre-check loop; sets `state.state = "error"` and raises HTTPException on failure | `test_disarm_nvr_failure` — FailingMockISAPIClient raises, asserts `state.state == "error"` and error detail in DB | Updates `nvr.last_seen_at` and `nvr.status = "online"` as side effect on success (NVR-05) |
| DARM-03 | SATISFIED | `service.py:192-199` — `for d_type in DETECTION_TYPES` with try/except; `snapshot_data[d_type] = xml` only on success | `test_disarm_success` (all 4 types fetched); `test_disarm_partial_failure` (camera with no successful GET causes error) | 404s and other non-200 silently skipped; only requires at least one successful GET |
| DARM-04 | SATISFIED | `service.py:206-222` — checks for existing snapshot by camera_id (any partition); uses `existing_any.snapshot_data` if present | `test_disarm_snapshot_protection` (direct snapshot pre-seed); `test_disarm_camera_already_disarmed_by_other_partition` (cross-partition copy) | **Extra scrutiny required.** Implementation copies from ANY existing snapshot for that camera — preserves original armed state even in multi-partition scenarios |
| DARM-05 | SATISFIED | `service.py:227-230` — `for d_type, xml in snapshot_data.items(): if _is_enabled_in_xml(xml): new_xml = _disable_in_xml(xml); await client.put_detection_config(...)` | `test_disarm_success` (MockISAPIClient.put_detection_config called; DB state verifies) | `_disable_in_xml` at `service.py:63-70` sets `<enabled>false</enabled>` while preserving all other XML structure |
| DARM-06 | SATISFIED | `service.py:233-244` — appends `partition_id` to `CameraDisarmRefcount.disarmed_by_partitions` | `test_disarm_success` asserts `part.id in refcount.disarmed_by_partitions`; `test_disarm_camera_already_disarmed_by_other_partition` verifies both IDs present after second disarm | Idempotent guard: `if partition_id not in refcount.disarmed_by_partitions` |
| DARM-07 | SATISFIED | `service.py:272-273` sets `scheduled_rearm_at`; `service.py:295-296` calls `await schedule_rearm(partition_id, state.scheduled_rearm_at)` | `test_disarm_calls_schedule_rearm_when_auto_rearm_minutes_set` — asserts `mock_sched.assert_called_once()` with correct partition_id | Only called when `partition.auto_rearm_minutes` is set and scheduled_rearm_at is not None |
| DARM-08 | SATISFIED | `service.py:278-289` — `PartitionAuditLog(action="disarm", ...)` with metadata dict containing `reason`, `cameras_disarmed`, `cameras_kept_disarmed_by_other_partition`, `errors_count` | `test_disarm_success` asserts `audits[0].action == "disarm"` and `audits[0].performed_by == "test-user"` | Failure path also logs `action="disarm_failed"` at `service.py:156-162` |
| DARM-09 | SATISFIED | `service.py:298-303` — `DisarmResponse(cameras_disarmed=..., cameras_kept_disarmed_by_other_partition=..., scheduled_rearm_at=..., errors=errors)` | `test_disarm_success` checks all fields; `test_disarm_camera_already_disarmed_by_other_partition` verifies counter split; `test_disarm_partial_failure` verifies errors list populated | Response always includes all four fields |
| DARM-10 | SATISFIED (code inspection) | `service.py:256` — `await asyncio.gather(*(process_camera(c) for c in cameras))` | No dedicated concurrency test — **structural behavior, inspection evidence per locked decision** | `asyncio.Lock()` at `service.py:172` protects concurrent DB writes; STATE.md records this design decision |

### ARM Group

| ID | Status | Code Location | Test(s) | Notes |
|----|--------|---------------|---------|-------|
| ARM-01 | SATISFIED | `routes.py:75-87` — `POST /{partition_id}/arm`; `ArmRequest` schema with `armed_by` | `test_arm_success_single_partition`, `test_arm_idempotent`, `test_arm_from_partial_state_succeeds`, `test_arm_from_error_state_succeeds` | Arm proceeds from `disarmed`, `partial`, `error` states; idempotent no-op from `armed` |
| ARM-02 | SATISFIED | `service.py:388-390` — `new_partitions.remove(partition_id); refcount.disarmed_by_partitions = new_partitions` | `test_arm_success_single_partition` asserts `len(refcount.disarmed_by_partitions) == 0`; `test_arm_multi_partition_stay_disarmed` asserts only `part2.id` remains | Guard at `service.py:384-386` skips cameras not disarmed by this partition |
| ARM-03 | SATISFIED | `service.py:403-411` — `if remaining_count == 0: for d_type, xml in snapshot.snapshot_data.items(): await client.put_detection_config(...); await db.delete(snapshot)` | `test_arm_success_single_partition` verifies `cameras_restored == 1` and snapshot deleted; `test_arm_restore_failure` verifies failure path | Restores original XML (not modified disabled version) from snapshot |
| ARM-04 | SATISFIED | `service.py:413-419` — `else: if snapshot: await db.delete(snapshot); cameras_kept_disarmed += 1` | `test_arm_multi_partition_stay_disarmed` verifies `cameras_kept_disarmed == 1` and part2 snapshot retained | Deletes this partition's snapshot but does not call `put_detection_config` |
| ARM-05 | SATISFIED | `service.py:318` — `await cancel_rearm(partition_id)` called unconditionally before any DB writes; `service.py:430` — `state.scheduled_rearm_at = None` | `test_arm_calls_cancel_rearm` asserts `mock_cancel.assert_called_once()` with correct partition_id; `test_arm_success_single_partition` asserts `state.scheduled_rearm_at is None` | Cancel is unconditional — fires even on idempotent arm |
| ARM-06 | SATISFIED | `service.py:434-443` — `PartitionAuditLog(action="arm", performed_by=armed_by, ...)` | `test_arm_creates_audit_log_entry` asserts `audit.performed_by == "test-user"` with `action == "arm"` | Metadata includes `cameras_restored`, `cameras_kept_disarmed`, `errors_count` |
| ARM-07 | SATISFIED | `service.py:447-451` — `ArmResponse(cameras_restored=..., cameras_kept_disarmed=..., errors=errors)` | `test_arm_success_single_partition` verifies all fields; `test_arm_restore_failure` verifies errors list | All three fields always present in response |

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Parallel async execution | Custom queue/pool | `asyncio.gather()` — already used at `service.py:256` and `service.py:424` | Standard asyncio, already implemented |
| Concurrent session access | Ad-hoc DB guards | `asyncio.Lock()` — already used at `service.py:172` | Prevents SQLAlchemy SAWarning on concurrent session use |
| Digest auth | Custom auth header | `httpx.DigestAuth` — already used at `client.py:33` | Handles nonce/challenge cycle automatically |

---

## Common Pitfalls

### Pitfall 1: DARM-04 Cross-Partition Snapshot Copy
**What goes wrong:** Auditor reads code as "check for existing snapshot for this partition, skip if found" — misses the second-level query that checks for any snapshot from any partition.
**Why it happens:** Two separate queries at `service.py:181-186` (partition-scoped) and `service.py:208-213` (camera-scoped). The first checks if this partition already has a snapshot (skip if so). The second looks for any other partition's snapshot to copy from.
**How to avoid:** Read both queries in sequence. The comment `# DARM-04: If ANY snapshot exists for this camera, use it` at `service.py:206` is the key evidence marker.

### Pitfall 2: DARM-10 Has No Concurrency Test
**What goes wrong:** Treating DARM-10 as UNSATISFIED because there is no test that spawns two concurrent disarm calls and verifies ordering.
**Why it happens:** True concurrency tests require async coordination and are rarely written for this pattern.
**How to avoid:** Per the locked evidence standard, structural behaviors (parallelism via `asyncio.gather`) are satisfied by code inspection. Document the `asyncio.gather()` call at `service.py:256` with the `asyncio.Lock()` protection as the evidence.

### Pitfall 3: ISAPI-03 Retry Scope
**What goes wrong:** Auditor checks only `get_detection_config` for retry logic and misses that `get_device_info`, `get_camera_channels`, and `put_detection_config` also have retry.
**Why it happens:** Phase 07 added retry to `get_device_info` and `get_camera_channels` (they were originally in Phase 01 without retry). Phase 02 added retry to `get_detection_config` and `put_detection_config`.
**How to avoid:** Verify all four methods in `client.py` for the try/except retry pattern.

### Pitfall 4: ARM-05 Cancel is Unconditional
**What goes wrong:** Auditor expects `cancel_rearm` to be called only when `scheduled_rearm_at` is set, and marks it PARTIAL if they do not find a conditional check.
**Why it happens:** The implementation at `service.py:318` calls `cancel_rearm` before the idempotency check — always fires.
**How to avoid:** This is intentional design per STATE.md: "cancel_rearm catches ScheduleLookupError (APScheduler 4.x) — not JobLookupError; autouse conftest fixture mocks service-level schedule_rearm/cancel_rearm for test isolation."

---

## Code Examples

### DARM-04 Snapshot Immutability (the tricky part)

```python
# app/partitions/service.py:178-222
# Phase 1: check if THIS partition already has a snapshot (idempotent skip)
stmt = select(CameraDetectionSnapshot).where(
    CameraDetectionSnapshot.camera_id == camera.id,
    CameraDetectionSnapshot.partition_id == partition_id,
)
res = await db.execute(stmt)
snapshot = res.scalar_one_or_none()

if not snapshot:
    # ... fetch all 4 detection types from ISAPI ...

    # Phase 2: DARM-04 — check for ANY snapshot from ANY partition
    stmt = select(CameraDetectionSnapshot).where(
        CameraDetectionSnapshot.camera_id == camera.id
    ).limit(1)
    res = await db.execute(stmt)
    existing_any = res.scalar_one_or_none()

    # If another partition's snapshot exists, use it (preserves original armed state)
    final_snapshot_data = existing_any.snapshot_data if existing_any else snapshot_data
```

### DARM-10 Parallelism (code inspection evidence)

```python
# app/partitions/service.py:172 — DB lock for concurrent session access
db_lock = asyncio.Lock()

# app/partitions/service.py:256 — parallel execution across cameras
await asyncio.gather(*(process_camera(c) for c in cameras))

# app/partitions/service.py:424 — same pattern in arm_partition
await asyncio.gather(*(process_camera(c) for c in cameras))
```

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 + pytest-asyncio 1.3.0 |
| Config file | pyproject.toml |
| Quick run command | `python3 -m pytest tests/test_isapi_client.py tests/test_disarm.py tests/test_arm.py -v` |
| Full suite command | `python3 -m pytest tests/ -v` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ISAPI-01 | DigestAuth instance | unit | `python3 -m pytest tests/test_isapi_client.py::test_client_uses_digest_auth_and_no_tls_verify -v` | Yes |
| ISAPI-02 | connect=5s, read=10s timeouts | unit | `python3 -m pytest tests/test_isapi_client.py::test_client_timeout_settings -v` | Yes |
| ISAPI-03 | Retry once on timeout, no retry on 4xx | unit | `python3 -m pytest tests/test_isapi_client.py -v` | Yes |
| ISAPI-04 | verify=False for self-signed TLS | unit | `python3 -m pytest tests/test_isapi_client.py::test_client_uses_digest_auth_and_no_tls_verify -v` | Yes |
| ISAPI-05 | XML parsing and manipulation | unit+integration | `python3 -m pytest tests/test_isapi_client.py tests/test_disarm.py -v` | Yes |
| DARM-01 | POST disarm endpoint exists | integration | `python3 -m pytest tests/test_disarm.py::test_disarm_success -v` | Yes |
| DARM-02 | NVR pre-check on disarm | integration | `python3 -m pytest tests/test_disarm.py::test_disarm_nvr_failure -v` | Yes |
| DARM-03 | Read all 4 detection endpoints | integration | `python3 -m pytest tests/test_disarm.py::test_disarm_success -v` | Yes |
| DARM-04 | Snapshot immutability | integration | `python3 -m pytest tests/test_disarm.py::test_disarm_snapshot_protection tests/test_disarm.py::test_disarm_camera_already_disarmed_by_other_partition -v` | Yes |
| DARM-05 | Disable enabled detections via PUT | integration | `python3 -m pytest tests/test_disarm.py::test_disarm_success -v` | Yes |
| DARM-06 | Refcount increment | integration | `python3 -m pytest tests/test_disarm.py::test_disarm_success -v` | Yes |
| DARM-07 | Schedule rearm when auto_rearm_minutes set | integration | `python3 -m pytest tests/test_disarm.py::test_disarm_calls_schedule_rearm_when_auto_rearm_minutes_set -v` | Yes |
| DARM-08 | Audit log on disarm | integration | `python3 -m pytest tests/test_disarm.py::test_disarm_success -v` | Yes |
| DARM-09 | Response fields (counts + errors) | integration | `python3 -m pytest tests/test_disarm.py -v` | Yes |
| DARM-10 | Parallel camera processing | inspection | `asyncio.gather()` at service.py:256 — no automated test; structural behavior | N/A |
| ARM-01 | POST arm endpoint exists, idempotent | integration | `python3 -m pytest tests/test_arm.py::test_arm_idempotent tests/test_arm.py::test_arm_from_partial_state_succeeds -v` | Yes |
| ARM-02 | Refcount decrement | integration | `python3 -m pytest tests/test_arm.py::test_arm_success_single_partition -v` | Yes |
| ARM-03 | Restore config + delete snapshot (refcount=0) | integration | `python3 -m pytest tests/test_arm.py::test_arm_success_single_partition -v` | Yes |
| ARM-04 | Stay disarmed (refcount>0) | integration | `python3 -m pytest tests/test_arm.py::test_arm_multi_partition_stay_disarmed -v` | Yes |
| ARM-05 | Cancel rearm job on arm | integration | `python3 -m pytest tests/test_arm.py::test_arm_calls_cancel_rearm -v` | Yes |
| ARM-06 | Audit log on arm | integration | `python3 -m pytest tests/test_arm.py::test_arm_creates_audit_log_entry -v` | Yes |
| ARM-07 | Response fields (counts + errors) | integration | `python3 -m pytest tests/test_arm.py::test_arm_restore_failure -v` | Yes |

### Sampling Rate
- **Per task commit:** `python3 -m pytest tests/test_isapi_client.py tests/test_disarm.py tests/test_arm.py -v`
- **Per wave merge:** `python3 -m pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
None — existing test infrastructure covers all phase requirements. This is a documentation-only phase (no new code expected unless gap found).

---

## Open Questions

1. **DARM-03: Does "saves only endpoints returning HTTP 200" include partial-success edge case?**
   - What we know: `found_any` must be true for disarm to succeed; individual endpoint failures are silently skipped
   - What's unclear: Whether the spec intends "at least one must succeed" or "record exactly those that succeed"
   - Recommendation: Current implementation satisfies both interpretations. Document as SATISFIED with note about the `found_any` guard.

2. **DARM-05: Are all detection types disabled, or only enabled ones?**
   - What we know: `_is_enabled_in_xml` gates each PUT — only issues PUT when `enabled=true`
   - What's unclear: Spec says "disables all detection types that were enabled=true" — this is consistent
   - Recommendation: SATISFIED. The guard is correct per spec language.

---

## Sources

### Primary (HIGH confidence)
- `app/isapi/client.py` — full source read; all ISAPI requirements verified directly
- `app/partitions/service.py` — full source read; all DARM and ARM requirements verified directly
- `app/partitions/routes.py` — full source read; endpoint existence for DARM-01 and ARM-01 verified
- `tests/test_isapi_client.py` — 17 tests collected; all ISAPI requirements have test coverage
- `tests/test_disarm.py` — 7 tests collected; all DARM requirements except DARM-10 have test coverage
- `tests/test_arm.py` — 8 tests collected; all ARM requirements have test coverage
- `.planning/phases/02-isapi-core-operations/02-VALIDATION.md` — existing requirement-to-test map cross-referenced
- `.planning/STATE.md` — Phase 02 decisions section referenced for design rationale evidence

### Secondary (MEDIUM confidence)
- `tests/conftest.py` — test infrastructure, scheduler mock pattern confirmed
- `tests/mocks.py` — MockISAPIClient signature matches ISAPIClient interface

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — source files read directly, no inference
- Architecture: HIGH — all 22 requirements traced to specific file:line locations
- Pitfalls: HIGH — based on direct code reading of the two highest-risk requirements (DARM-04, DARM-10)

**Research date:** 2026-03-17
**Valid until:** Stable — code has not changed since Phase 07; valid until next code modification to `app/isapi/client.py` or `app/partitions/service.py`
