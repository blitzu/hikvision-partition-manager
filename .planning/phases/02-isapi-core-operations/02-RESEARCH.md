# Phase 02: ISAPI Core Operations — Research

**Researched:** 2026-03-18
**Domain:** Hikvision ISAPI HTTP client, partition arm/disarm business logic, multi-partition refcount
**Confidence:** HIGH — Implementation is complete and retroverified. All findings come from reading the production source and test files directly.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Partial Failure State**
- Partition state = `partial` when some cameras succeed and others fail during disarm (not `error`)
- `error` state reserved for full failure (e.g., NVR pre-check fails before any ISAPI calls)
- POST arm always proceeds regardless of current state (`partial`, `error`, or `disarmed`) — arm is never blocked
- Only one retry per camera, on timeout only (ISAPI-03) — non-timeout failures (4xx, 5xx) are not retried
- Error list items in disarm/arm response contain: `camera_id` + HTTP status + raw ISAPI error message

**NVR Connectivity Pre-Check (DARM-02)**
- If ANY NVR involved in the partition is unreachable, the whole disarm fails immediately — state=error, no partial disarming
- Pre-check uses `ISAPIClient.get_device_info()` — same GET /ISAPI/System/deviceInfo as the connectivity test endpoint
- Pre-check updates `nvr.last_seen_at` and `nvr.status` as a side effect (consistent with NVR-05)

**Disarm/Arm Idempotency**
- POST disarm on already-disarmed partition: graceful no-op — HTTP 200 + `{ success: true, data: { cameras_disarmed: 0, ... } }`
- POST arm on already-armed partition: graceful no-op — HTTP 200 + `{ success: true, data: { cameras_restored: 0, ... } }`
- Safe for duplicate VMS requests; no error returned for repeated calls

**Business Logic Placement**
- Disarm/arm logic lives in `app/partitions/` — `routes.py` for HTTP endpoints, `service.py` for business logic
- Consistent with the feature/domain module pattern established in Phase 1
- Phase 3 partition CRUD routes also go in `app/partitions/routes.py`

### Claude's Discretion
- Internal structure of disarm/arm service functions
- How parallelism is implemented for same-NVR cameras (asyncio.gather)
- XML parsing for the 4 detection type endpoints

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ISAPI-01 | All ISAPI calls use HTTP Digest Authentication (not Basic) | `httpx.DigestAuth` passed to every `AsyncClient(**self._client_kwargs)` |
| ISAPI-02 | Connection timeout 5s; read timeout 10s | `httpx.Timeout(10.0, connect=5.0, read=10.0)` in `_client_kwargs` |
| ISAPI-03 | Retry once on timeout | Inline try/except `httpx.TimeoutException` in each method |
| ISAPI-04 | Accept self-signed TLS certs | `"verify": False` in `_client_kwargs` |
| ISAPI-05 | Parse XML responses (not JSON) | `xml.etree.ElementTree` for device/channel info; raw XML string returned for detection configs |
| DARM-01 | POST disarm endpoint | `@router.post("/{partition_id}/disarm")` in `app/partitions/routes.py` |
| DARM-02 | NVR pre-check before disarm | `get_device_info()` call on each NVR before per-camera work begins |
| DARM-03 | Read all 4 ISAPI detection endpoints | `DETECTION_TYPES = ["MotionDetection", "LineDetection", "FieldDetection", "shelteralarm"]` loop in `process_camera` |
| DARM-04 | Snapshot immutability (do not overwrite existing) | Two-stage check: partition-scoped then camera-scoped-any; existing data wins |
| DARM-05 | Disable enabled detections via PUT | `_is_enabled_in_xml` gate + `_disable_in_xml` + `put_detection_config` |
| DARM-06 | Refcount increment | Append partition_id to `CameraDisarmRefcount.disarmed_by_partitions` |
| DARM-07 | Schedule auto-rearm | `schedule_rearm(partition_id, state.scheduled_rearm_at)` after commit |
| DARM-08 | Audit log on disarm | `PartitionAuditLog(action="disarm")` always appended |
| DARM-09 | Response includes counts + errors | `DisarmResponse` schema with all required fields |
| DARM-10 | Parallel ISAPI calls per NVR | `asyncio.gather(*coroutines)` + `asyncio.Lock` for DB writes |
| ARM-01 | POST arm endpoint | `@router.post("/{partition_id}/arm")` in routes.py |
| ARM-02 | Refcount decrement | `list.remove(partition_id)` then reassign to trigger dirty-tracking |
| ARM-03 | Restore detection when refcount reaches 0 | `put_detection_config` with original XML; then `db.delete(snapshot)` |
| ARM-04 | Stay disarmed when refcount > 0 | No PUT issued; snapshot for this partition deleted; camera detection left disabled |
| ARM-05 | Cancel pending rearm on arm | `cancel_rearm(partition_id)` called unconditionally before any idempotency check |
| ARM-06 | Audit log on arm | `PartitionAuditLog(action="arm")` always appended |
| ARM-07 | Response includes counts + errors | `ArmResponse` schema with all required fields |
</phase_requirements>

---

## Summary

Phase 02 implements the Hikvision ISAPI HTTP client extension and the complete partition disarm/arm business logic. The implementation is **already complete and retroverified** as of 2026-03-17 (Phase 08 retroverification). All 22 requirements are satisfied by the production code in `app/isapi/client.py` and `app/partitions/service.py`, tested by 32 tests across `tests/test_isapi_client.py`, `tests/test_disarm.py`, and `tests/test_arm.py`.

The domain involves three interlocking concerns: (1) an ISAPI HTTP client that uses Digest auth, disables TLS verification, enforces 5s/10s timeouts, and retries exactly once on timeout; (2) a disarm operation that snapshots current camera detection state, disables active detections in parallel, and tracks multi-partition refcounts; (3) an arm operation that decrements refcounts, conditionally restores detection from snapshot when refcount reaches zero, and cancels scheduled auto-rearm jobs.

The central correctness challenge is snapshot immutability (DARM-04): a camera disarmed by two partitions must always restore from the original armed-state snapshot, not from the already-disabled state captured by the second disarm. The implementation resolves this by a two-stage check — partition-scoped first, then camera-scoped-any — and always prefers the oldest existing snapshot data over fresh ISAPI reads.

**Primary recommendation:** The implementation is complete. Any planning for this phase focuses on retroverification or gap-closure; no new implementation is required.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| httpx | 0.28+ | Async ISAPI HTTP calls | Native async, DigestAuth support, clean Timeout API |
| httpx.DigestAuth | built-in | HTTP Digest auth against NVRs | NVR firmware requires Digest, not Basic |
| httpx.Timeout | built-in | Per-request connect/read timeouts | Positional default arg required in 0.28+ |
| xml.etree.ElementTree | stdlib | XML parsing | NVR responses are XML only, no JSON |
| asyncio.gather | stdlib | Parallel per-camera ISAPI calls | Fan-out N coroutines, await all; meets DARM-10 |
| asyncio.Lock | stdlib | Serialize AsyncSession DB writes | Prevents SAWarning from concurrent session mutation |
| SQLAlchemy AsyncSession | project standard | Async ORM queries | Established in Phase 1 |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| app.core.crypto.decrypt_password | project | Recover NVR password before ISAPI call | Every time an ISAPIClient is constructed |
| app.core.inflight | project | Track in-flight ISAPI calls for graceful shutdown | Every ISAPIClient method via `_track_inflight()` context manager |
| app.jobs.auto_rearm | project | Schedule / cancel auto-rearm APScheduler jobs | After disarm commit; unconditionally before arm idempotency check |

### Installation
All dependencies are already installed in the project. No new packages needed for Phase 02.

---

## Architecture Patterns

### Module Structure
```
app/
├── isapi/
│   └── client.py        # ISAPIClient — all NVR HTTP operations
├── partitions/
│   ├── models.py        # All 9 ORM models (already exist)
│   ├── routes.py        # HTTP endpoints: /disarm, /arm, future CRUD
│   ├── schemas.py       # DisarmRequest, ArmRequest, DisarmResponse, ArmResponse, PartitionError
│   └── service.py       # disarm_partition(), arm_partition() + XML helpers
tests/
├── mocks.py             # MockISAPIClient — drop-in for service monkeypatching
├── test_isapi_client.py # Unit tests for ISAPIClient (no DB)
├── test_disarm.py       # Integration tests for disarm (DB + MockISAPIClient)
└── test_arm.py          # Integration tests for arm (DB + MockISAPIClient)
```

### Pattern 1: ISAPIClient Method Structure (Retry + Inflight Tracking)
**What:** Every ISAPIClient method follows a fixed 4-part structure.
**When to use:** Adding any new ISAPI endpoint method.

```python
# Source: app/isapi/client.py
async def get_detection_config(self, channel_no: int, detection_type: str) -> str:
    url = self._detection_url(channel_no, detection_type)
    async with _track_inflight():                        # 1. inflight tracking
        async with httpx.AsyncClient(**self._client_kwargs) as client:
            try:
                resp = await client.get(url)             # 2. first attempt
            except httpx.TimeoutException:
                resp = await client.get(url)             # 3. one retry on timeout only
            resp.raise_for_status()                      # 4. raise on 4xx/5xx (no retry)
            return resp.text
```

Key detail: `httpx.Timeout(10.0, connect=5.0, read=10.0)` — the positional `10.0` is the default timeout, required in httpx 0.28+. The retry is inline try/except, not a decorator, to preserve the single-retry-only semantics cleanly.

### Pattern 2: Detection URL Routing
**What:** `_detection_url()` dispatches to Smart or basic motion endpoint based on type.
**When to use:** All 4 standard detection types use `/ISAPI/Smart/{type}/channels/{id}`; `BASIC_MOTION` uses `/ISAPI/System/Video/inputs/channels/{id}/motionDetection`.

```python
# Source: app/isapi/client.py
BASIC_MOTION = "basicMotionDetection"

def _detection_url(self, channel_no: int, detection_type: str) -> str:
    if detection_type == self.BASIC_MOTION:
        return f"{self.base_url}/ISAPI/System/Video/inputs/channels/{channel_no}/motionDetection"
    return f"{self.base_url}/ISAPI/Smart/{detection_type}/channels/{channel_no}"
```

The fallback flow in disarm: try all 4 Smart types first; if ALL fail (4xx/5xx), try `BASIC_MOTION`. If that also fails, camera is an error.

### Pattern 3: Disarm process_camera Parallelism
**What:** Per-camera coroutines run concurrently via asyncio.gather; DB writes serialized via asyncio.Lock.
**When to use:** Any fan-out over cameras where ISAPI calls dominate latency.

```python
# Source: app/partitions/service.py
db_lock = asyncio.Lock()

async def process_camera(camera: Camera):
    # ISAPI calls — no lock needed, purely network I/O
    xml = await client.get_detection_config(camera.channel_no, d_type)

    async with db_lock:      # Serialize only the DB mutations
        db.add(snapshot)
        ...

await asyncio.gather(*(process_camera(c) for c in cameras))
```

### Pattern 4: Snapshot Immutability (DARM-04)
**What:** Two-stage check before creating a snapshot record.
**When to use:** Disarm — must never overwrite original armed-state snapshot.

```python
# Source: app/partitions/service.py (simplified)
# Stage 1: Does THIS partition already have a snapshot for this camera?
snapshot = await db.execute(
    select(CameraDetectionSnapshot).where(
        CameraDetectionSnapshot.camera_id == camera.id,
        CameraDetectionSnapshot.partition_id == partition_id,
    )
).scalar_one_or_none()

if not snapshot:
    # Fetch live ISAPI data ...
    snapshot_data = {d_type: xml for ...}

    # Stage 2: Does ANY partition have a snapshot for this camera?
    existing_any = await db.execute(
        select(CameraDetectionSnapshot).where(
            CameraDetectionSnapshot.camera_id == camera.id
        ).limit(1)
    ).scalar_one_or_none()

    # Always use the oldest snapshot's data — preserves original armed state
    final_data = existing_any.snapshot_data if existing_any else snapshot_data
    snapshot = CameraDetectionSnapshot(..., snapshot_data=final_data)
    db.add(snapshot)
```

### Pattern 5: XML Disable via Regex (not re-serialize)
**What:** `_disable_in_xml` uses regex replacement, not ET.tostring(), to modify the XML.
**When to use:** Producing PUT bodies for NVRs — re-serializing with ET mangles Hikvision namespace prefixes and causes 400 Bad Request.

```python
# Source: app/partitions/service.py
def _disable_in_xml(xml_text: str) -> str:
    return re.sub(
        r"(<(?:[^:>]+:)?enabled\s*>)\s*true\s*(</(?:[^:>]+:)?enabled\s*>)",
        r"\g<1>false\2",
        xml_text,
        flags=re.IGNORECASE,
    )
```

### Pattern 6: Refcount Array Mutation
**What:** PostgreSQL ARRAY(UUID) column must be assigned a new Python list to trigger SQLAlchemy dirty-tracking.
**When to use:** Any mutation of `disarmed_by_partitions`.

```python
# Source: app/partitions/service.py
new_partitions = list(refcount.disarmed_by_partitions)  # copy
new_partitions.append(partition_id)                     # mutate copy
refcount.disarmed_by_partitions = new_partitions        # reassign to trigger dirty-tracking
```

### Pattern 7: Mock Injection for Integration Tests
**What:** `monkeypatch.setattr("app.partitions.service.ISAPIClient", MockISAPIClient)` replaces the class at import time.
**When to use:** Any integration test that runs real DB + HTTP routes but must not hit real NVRs.

```python
# Source: tests/test_disarm.py
@pytest.fixture
def mock_isapi(monkeypatch):
    monkeypatch.setattr("app.partitions.service.ISAPIClient", MockISAPIClient)
```

### Anti-Patterns to Avoid
- **Re-serializing NVR XML with ET.tostring():** Mangles Hikvision namespace prefixes, causes 400 Bad Request on PUT. Use regex replacement instead.
- **Decorator-based retry with multiple retries:** ISAPI-03 requires exactly one retry on timeout. A generic retry decorator risks retrying too many times or retrying non-timeout errors.
- **Global asyncio.Lock for the whole disarm operation:** Lock should only protect DB write sections inside `process_camera`, not the ISAPI network calls. Locking ISAPI calls eliminates the parallelism benefit.
- **Overwriting existing snapshot data on second disarm:** Second disarm must detect an existing snapshot and skip the ISAPI fetch entirely, preserving the original armed state.
- **Raising error when refcount decrement finds camera not in list:** If a camera was never disarmed by this partition (e.g., added to partition after a disarm), `arm_partition` should silently skip it with an early return.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP Digest auth | Custom HMAC/MD5 auth headers | `httpx.DigestAuth` | 7-step challenge-response with nonce, cnonce, qop; one-liner with httpx |
| TLS cert bypass | Custom SSL context | `httpx.AsyncClient(verify=False)` | Already in `_client_kwargs`; one flag |
| Timeout management | Custom asyncio timeout wrappers | `httpx.Timeout(10.0, connect=5.0, read=10.0)` | Client-level timeout applies to all requests |
| In-flight tracking | Custom counter class | `app.core.inflight` module | Already used by ISAPIClient; `_track_inflight()` context manager handles increment/decrement |
| XML enabled check | String search | `_is_enabled_in_xml(xml)` helper | Namespace-aware ET parse; handles case variation |
| XML disable | String replace | `_disable_in_xml(xml)` regex helper | Preserves NVR namespace prefixes that ET.tostring() destroys |

---

## Common Pitfalls

### Pitfall 1: httpx.Timeout Positional Argument (httpx 0.28+)
**What goes wrong:** `httpx.Timeout(connect=5.0, read=10.0)` raises a TypeError — the positional default timeout is now required.
**Why it happens:** httpx 0.28 changed the Timeout constructor signature.
**How to avoid:** Always use `httpx.Timeout(10.0, connect=5.0, read=10.0)`.
**Warning signs:** `TypeError: Timeout.__init__() missing 1 required positional argument`.

### Pitfall 2: ET.tostring() Mangles Hikvision Namespace Prefixes
**What goes wrong:** Parsing detection XML with ElementTree and re-serializing with `ET.tostring()` strips or changes namespace prefix declarations. The NVR rejects the PUT with 400 Bad Request.
**Why it happens:** Hikvision firmware is strict about namespace declarations in the XML root element. ET normalizes them.
**How to avoid:** Use regex replacement (`_disable_in_xml`) to modify XML in-place without re-parsing and re-serializing.
**Warning signs:** PUT succeeds in tests (mocked) but fails against real NVR with HTTP 400.

### Pitfall 3: asyncio.Lock Scope Too Wide
**What goes wrong:** Holding `db_lock` during ISAPI GET/PUT calls serializes all camera processing, making the operation as slow as sequential.
**Why it happens:** Lock acquired at the top of `process_camera` and held through network calls.
**How to avoid:** Acquire lock only for DB mutation blocks inside `process_camera`; ISAPI calls happen outside the lock.
**Warning signs:** Disarm of a 10-camera partition takes 10x as long as expected.

### Pitfall 4: Snapshot Overwrite on Second Disarm
**What goes wrong:** Second disarm call (same partition) fetches fresh ISAPI data — which is now the disabled state — and overwrites the snapshot with `enabled=false` XML. When the partition arms, detection is "restored" to disabled.
**Why it happens:** Missing partition-scoped snapshot check before issuing ISAPI GETs.
**How to avoid:** Query for existing partition-scoped snapshot before any ISAPI call. If found, skip ISAPI entirely and use existing data.
**Warning signs:** After disarm → arm → disarm cycle, cameras stay disabled after the second arm.

### Pitfall 5: APScheduler 4.x API Differences
**What goes wrong:** `ScheduleLookupError` is not caught when cancel_rearm is called on a partition with no scheduled job. Alternatively, `add_job` is used for recurring jobs (it is one-shot only in APScheduler 4.x).
**Why it happens:** APScheduler 4.x API changed from 3.x: `add_schedule` replaces `add_job` for recurring; `ScheduleLookupError` replaces `JobLookupError` for lookup failures.
**How to avoid:** Catch `ScheduleLookupError` (not `JobLookupError`) in `cancel_rearm`. Use `add_schedule` + `IntervalTrigger` for recurring, `DateTrigger` for one-shot.
**Warning signs:** `cancel_rearm` crashes when called on an armed partition; or monitor jobs fire once and stop.

### Pitfall 6: Concurrent AsyncSession Writes Without Lock
**What goes wrong:** `asyncio.gather` runs multiple `process_camera` coroutines; if two coroutines issue `db.add()` or `db.delete()` simultaneously without a lock, SQLAlchemy emits SAWarning about concurrent access to the same session.
**Why it happens:** AsyncSession is not thread-safe and not safe for concurrent coroutine access without serialization.
**How to avoid:** Wrap all `db.add()`, `db.execute()`, `db.delete()` inside `process_camera` with `async with db_lock:`.
**Warning signs:** SAWarning logs like "Object ... is already attached to session".

---

## Code Examples

Verified patterns from production source:

### ISAPIClient Construction
```python
# Source: app/isapi/client.py
self._auth = httpx.DigestAuth(username, password)
self._client_kwargs: dict = {
    "auth": self._auth,
    "verify": False,          # NVRs commonly use self-signed certs
    "timeout": httpx.Timeout(10.0, connect=5.0, read=10.0),
}
```

### Detection Type Constants
```python
# Source: app/partitions/service.py
DETECTION_TYPES = [
    "MotionDetection",
    "LineDetection",
    "FieldDetection",
    "shelteralarm",
]
# Fallback for cameras that don't support Smart endpoints:
ISAPIClient.BASIC_MOTION = "basicMotionDetection"
```

### Disarm Idempotency Guard
```python
# Source: app/partitions/service.py
if state.state == "disarmed":
    return DisarmResponse(
        cameras_disarmed=0,
        cameras_kept_disarmed_by_other_partition=0,
        scheduled_rearm_at=state.scheduled_rearm_at,
    )
```

### Arm Cancel Rearm (Unconditional)
```python
# Source: app/partitions/service.py — called BEFORE idempotency check
await cancel_rearm(partition_id)
```

### NVR Pre-check with Side Effect
```python
# Source: app/partitions/service.py
await client.get_device_info()
nvr.status = "online"
nvr.last_seen_at = datetime.now(timezone.utc)
nvr_clients[nvr_id] = client
```

### Refcount Decrement with Early Return
```python
# Source: app/partitions/service.py
if not refcount or partition_id not in refcount.disarmed_by_partitions:
    return  # Camera was not disarmed by this partition — skip silently

new_partitions = list(refcount.disarmed_by_partitions)
new_partitions.remove(partition_id)
refcount.disarmed_by_partitions = new_partitions
remaining_count = len(new_partitions)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Basic auth for ISAPI | Digest auth (`httpx.DigestAuth`) | Phase 02 | NVRs require Digest; Basic returns 401 |
| `httpx.Timeout(connect=5.0, read=10.0)` (no positional) | `httpx.Timeout(10.0, connect=5.0, read=10.0)` | httpx 0.28 | Without positional arg: TypeError at runtime |
| ET.tostring() for XML modification | Regex replacement (`re.sub`) | Phase 02 (c0faff2) | ET mangles NVR namespace prefixes → 400 on PUT |
| Sequential per-camera ISAPI calls | asyncio.gather + asyncio.Lock | Phase 02 | Meets DARM-10; practical speedup for multi-camera partitions |
| APScheduler 3.x `add_job` / `JobLookupError` | APScheduler 4.x `add_schedule` / `ScheduleLookupError` | Phase 04 | Wrong API crashes scheduler at runtime |

---

## Open Questions

None — the implementation is complete. All requirements are satisfied and retroverified.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio 0.23.x |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` — `asyncio_mode = "auto"`, `testpaths = ["tests"]` |
| Quick run command | `python3 -m pytest tests/test_isapi_client.py tests/test_disarm.py tests/test_arm.py -x -q` |
| Full suite command | `python3 -m pytest tests/ -x -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ISAPI-01 | DigestAuth used on all requests | unit | `python3 -m pytest tests/test_isapi_client.py::test_client_uses_digest_auth_and_no_tls_verify -x` | Yes |
| ISAPI-02 | Timeout connect=5s read=10s | unit | `python3 -m pytest tests/test_isapi_client.py::test_client_timeout_settings -x` | Yes |
| ISAPI-03 | Retry once on timeout | unit | `python3 -m pytest tests/test_isapi_client.py -k "retry" -x` | Yes |
| ISAPI-04 | verify=False in client_kwargs | unit | `python3 -m pytest tests/test_isapi_client.py::test_client_uses_digest_auth_and_no_tls_verify -x` | Yes |
| ISAPI-05 | XML responses parsed | unit | `python3 -m pytest tests/test_isapi_client.py::test_get_detection_config_success_returns_xml -x` | Yes |
| DARM-01 | POST /disarm endpoint | integration | `python3 -m pytest tests/test_disarm.py::test_disarm_success -x` | Yes |
| DARM-02 | NVR pre-check fails → state=error | integration | `python3 -m pytest tests/test_disarm.py::test_disarm_nvr_failure -x` | Yes |
| DARM-03 | Read all 4 detection types | integration | `python3 -m pytest tests/test_disarm.py::test_disarm_success -x` | Yes |
| DARM-04 | Snapshot immutability | integration | `python3 -m pytest tests/test_disarm.py::test_disarm_snapshot_protection tests/test_disarm.py::test_disarm_camera_already_disarmed_by_other_partition -x` | Yes |
| DARM-05 | Disable enabled detections via PUT | integration | `python3 -m pytest tests/test_disarm.py::test_disarm_success -x` | Yes |
| DARM-06 | Refcount increment | integration | `python3 -m pytest tests/test_disarm.py::test_disarm_success -x` | Yes |
| DARM-07 | Schedule auto-rearm | integration | `python3 -m pytest tests/test_disarm.py::test_disarm_calls_schedule_rearm_when_auto_rearm_minutes_set -x` | Yes |
| DARM-08 | Audit log on disarm | integration | `python3 -m pytest tests/test_disarm.py::test_disarm_success -x` | Yes |
| DARM-09 | Response field coverage | integration | `python3 -m pytest tests/test_disarm.py -x` | Yes |
| DARM-10 | Parallel ISAPI calls | inspection | N/A — structural behavior; asyncio.gather + asyncio.Lock verified by code inspection | Yes |
| ARM-01 | POST /arm endpoint | integration | `python3 -m pytest tests/test_arm.py::test_arm_success_single_partition -x` | Yes |
| ARM-02 | Refcount decrement | integration | `python3 -m pytest tests/test_arm.py::test_arm_success_single_partition -x` | Yes |
| ARM-03 | Restore detection when refcount=0 | integration | `python3 -m pytest tests/test_arm.py::test_arm_success_single_partition -x` | Yes |
| ARM-04 | Stay disarmed when refcount>0 | integration | `python3 -m pytest tests/test_arm.py::test_arm_multi_partition_stay_disarmed -x` | Yes |
| ARM-05 | Cancel rearm on arm | integration | `python3 -m pytest tests/test_arm.py::test_arm_calls_cancel_rearm -x` | Yes |
| ARM-06 | Audit log on arm | integration | `python3 -m pytest tests/test_arm.py::test_arm_creates_audit_log_entry -x` | Yes |
| ARM-07 | Response field coverage | integration | `python3 -m pytest tests/test_arm.py -x` | Yes |

### Sampling Rate
- **Per task commit:** `python3 -m pytest tests/test_isapi_client.py tests/test_disarm.py tests/test_arm.py -x -q`
- **Per wave merge:** `python3 -m pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
None — existing test infrastructure covers all phase requirements. All 32 tests exist and pass.

---

## Sources

### Primary (HIGH confidence)
- `app/isapi/client.py` — Full ISAPIClient implementation including DigestAuth, timeouts, retry, detection URL routing
- `app/partitions/service.py` — Complete disarm/arm business logic, XML helpers, refcount management, snapshot immutability
- `tests/test_isapi_client.py` — 17 unit tests for ISAPIClient
- `tests/test_disarm.py` — 7 integration tests for disarm operation
- `tests/test_arm.py` — 8 integration tests for arm operation
- `tests/mocks.py` — MockISAPIClient pattern
- `tests/conftest.py` — Test fixtures: engine, db_session, client, mock_scheduler_calls
- `.planning/phases/02-isapi-core-operations/02-VERIFICATION.md` — Retroverification report (2026-03-17), all 22 requirements satisfied

### Secondary (MEDIUM confidence)
- `STATE.md` — Accumulated decisions from all phases including Phase 02 ISAPI-specific decisions
- `.planning/phases/02-isapi-core-operations/02-CONTEXT.md` — Original locked decisions from discuss-phase

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — read directly from production source
- Architecture: HIGH — read from production source and test files
- Pitfalls: HIGH — read from STATE.md accumulated decisions and VERIFICATION.md retroverification notes

**Research date:** 2026-03-18
**Valid until:** 2026-06-18 (stable implementation; only changes if requirements change)
