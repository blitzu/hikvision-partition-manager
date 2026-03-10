# Phase 2: ISAPI Core Operations - Context

**Gathered:** 2026-03-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Disarming a partition disables detection on all member cameras via ISAPI; arming restores exact saved state respecting multi-partition refcount. Covers: extending ISAPIClient with Digest auth retry + detection endpoints, disarm operation (snapshot, refcount increment, parallel ISAPI writes), arm operation (refcount decrement, conditional restore, snapshot deletion). No partition CRUD, no REST API surface — those are Phase 3.

</domain>

<decisions>
## Implementation Decisions

### Partial Failure State
- Partition state = `partial` when some cameras succeed and others fail during disarm (not `error`)
- `error` state is reserved for full failure (e.g., NVR pre-check fails before any ISAPI calls)
- POST arm always proceeds regardless of current state (`partial`, `error`, or `disarmed`) — arm is never blocked
- Only one retry per camera, on timeout only (per ISAPI-03) — non-timeout failures (4xx, 5xx) are not retried
- Error list items in disarm/arm response contain: `camera_id` + HTTP status + raw ISAPI error message

### NVR Connectivity Pre-Check (DARM-02)
- If ANY NVR involved in the partition is unreachable, the whole disarm fails immediately — state=error, no partial disarming
- Pre-check uses `ISAPIClient.get_device_info()` — same GET /ISAPI/System/deviceInfo as the connectivity test endpoint
- Pre-check updates `nvr.last_seen_at` and `nvr.status` as a side effect (consistent with NVR-05)

### Disarm/Arm Idempotency
- POST disarm on already-disarmed partition: graceful no-op — HTTP 200 + `{ success: true, data: { cameras_disarmed: 0, ... } }`
- POST arm on already-armed partition: graceful no-op — HTTP 200 + `{ success: true, data: { cameras_restored: 0, ... } }`
- Safe for duplicate VMS requests; no error returned for repeated calls

### Business Logic Placement
- Disarm/arm logic lives in `app/partitions/` — `routes.py` for HTTP endpoints, `service.py` for business logic
- Consistent with the feature/domain module pattern established in Phase 1
- Phase 3 partition CRUD routes also go in `app/partitions/routes.py`

### Claude's Discretion
- Internal structure of disarm/arm service functions
- How parallelism is implemented for same-NVR cameras (asyncio.gather)
- XML parsing for the 4 detection type endpoints

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/isapi/client.py` — ISAPIClient class with `get_device_info()` and `get_camera_channels()`; designed as extension point. Add methods: `get_detection_config(channel)`, `put_detection_config(channel, xml)` for each of the 4 detection types. Do NOT restructure.
- `app/core/crypto.py` — `decrypt_password()` needed to recover NVR credentials before ISAPI calls
- `app/core/schemas.py` — `APIResponse[T]` envelope used by all existing routes
- `app/partitions/models.py` — All 9 models already exist: `Partition`, `PartitionCamera`, `PartitionState` (with `armed/disarmed/error/partial` enum), `CameraDetectionSnapshot` (JSONB), `CameraDisarmRefcount` (ARRAY(UUID)), `PartitionAuditLog`

### Established Patterns
- Feature/domain modules: `routes.py` + `schemas.py` per domain; add `service.py` for disarm/arm logic
- AsyncSession + asyncpg via `Depends(get_db)` — all DB access async
- `APIResponse[T]` envelope on all endpoints: `{ success, data, error }`
- NVR password decryption: `decrypt_password(nvr.password_encrypted)` before any ISAPI call
- `nvr.last_seen_at = datetime.now(UTC); nvr.status = "online"` after every successful ISAPI contact

### Integration Points
- `app/isapi/client.py` → extend with detection type methods (Phase 2 adds them)
- `app/partitions/routes.py` → new file; register router in `app/main.py`
- `app/nvrs/models.py` — NVRDevice needed to resolve cameras → NVRs for ISAPI calls
- `app/cameras/models.py` — Camera model; join via PartitionCamera to get cameras in a partition

</code_context>

<specifics>
## Specific Ideas

- No specific UI/UX references — this is pure API/logic phase
- The `partial` state is intentional and meaningful on the dashboard (Phase 5 will highlight it)

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 02-isapi-core-operations*
*Context gathered: 2026-03-10*
