# Phase 4: Automation & Alerts - Context

**Gathered:** 2026-03-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Background automation layer: APScheduler jobs for auto-rearm (on schedule), stuck-disarmed monitoring
(every 5 min), and NVR health checking (every 60s). Webhook delivery for 3 alert types. No new REST
API endpoints — all state is already exposed via Phase 3's partition and dashboard endpoints.

</domain>

<decisions>
## Implementation Decisions

### Job Persistence
- Use APScheduler with **PostgreSQL job store** (SQLAlchemyJobStore backed by the existing DB)
- Jobs survive process restarts and deploys
- On startup: **reconcile DB state** — query all partitions where `scheduled_rearm_at` is set and
  state is `disarmed`, re-register any jobs not already in the job store
- Missed jobs (scheduled time passed while service was down): **fire immediately on startup**
  (APScheduler default misfire behavior — partition gets rearmed promptly even if late)
- Scheduler wired into **FastAPI lifespan** in `app/main.py` — `scheduler.start()` after migrations,
  `scheduler.shutdown()` on exit

### Webhook Failure Behavior
- **3 retries with backoff** (1s, 5s, 15s delays) before giving up
- Delivery is **non-blocking** — fired as `asyncio.create_task`, job completes regardless of webhook outcome
- Failures go to **application logs only** — partition state and audit log unaffected
- **5 second timeout** per webhook attempt
- Claude's discretion: exact retry implementation (httpx with manual loop or tenacity)

### NVR Recovery Alerts
- Alert on **both offline AND online** transitions — send `nvr_online` webhook when NVR comes back
- **Cooldown: 5 minutes** between offline alerts — if an NVR already fired an offline alert in the
  last 5 min, suppress the next one (prevents flapping spam)
- **1 failed health check = offline** — no consecutive-failure buffer; mark offline immediately and
  fire webhook on first failure

### Stuck Monitor Behavior
- Fire alert **every 5 minutes** while partition remains stuck disarmed past threshold (spec behavior)
- Alerts continue **indefinitely until the partition is rearmed** — no cap
- One alert per affected partition per cycle (not one global "N partitions stuck" batch)

### Claude's Discretion
- Exact retry implementation for webhook delivery (manual loop vs tenacity)
- APScheduler job ID naming convention
- Whether to use `AsyncScheduler` (APScheduler 4.x) or `BackgroundScheduler` with asyncio bridge
- NVR cooldown tracking mechanism (in-memory dict vs DB column)

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ISAPIClient.get_device_info()` — already used for NVR connectivity test; reuse for health check ping
- `arm_partition()` in `app/partitions/service.py` — already clears `scheduled_rearm_at = None`; auto-rearm job calls this directly with `performed_by='system:auto_rearm'`
- `app/core/database.py` — async session factory already set up; job functions need their own session

### Established Patterns
- `asyncio.to_thread()` used in lifespan for sync Alembic; scheduler.start() is sync too — same pattern applies
- `asyncio.Lock` used in disarm loop — relevant if job functions touch shared state concurrently
- All NVR passwords decrypted via `decrypt_password()` before ISAPIClient instantiation — health check must do the same

### Integration Points
- `app/main.py` lifespan — add scheduler init/shutdown here
- `app/partitions/service.py` `arm_partition()` — auto-rearm job calls this
- `app/nvrs/` models — NVR health check reads `NVRDevice` rows, updates `status` and `last_seen_at`
- New module: `app/jobs/` — scheduler instance, job functions, webhook delivery utility

</code_context>

<specifics>
## Specific Ideas

- No specific UX references — this is a background automation layer with no user-visible surface
- Webhook payloads are fully specified in REQUIREMENTS.md (ALRT-01, ALRT-02, ALRT-03)

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 04-automation-alerts*
*Context gathered: 2026-03-10*
