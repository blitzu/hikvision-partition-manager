# Phase 6: Infrastructure - Context

**Gathered:** 2026-03-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Ship the service: Docker Compose deployment (app + postgres, zero manual steps), multi-stage
Dockerfile with non-root user, structured JSON logging, graceful shutdown with ISAPI drain,
parameterized query audit, .env.example, and README.md. No new features — this phase makes
the service deployable and understandable.

</domain>

<decisions>
## Implementation Decisions

### README Audience & Structure
- **Two audiences, separate sections**: Quick Start (developer cloning for local run) +
  Integration Guide (operator connecting an existing VMS).
- **VMS Integration Guide**: curl examples for POST disarm, POST arm, GET state, GET
  dashboard. Plus a narrative workflow: "When an alarm fires: 1. POST /disarm with
  disarmed_by 2. Monitor state via GET /state 3. POST /arm when event clears".
- **Refcount explanation**: Detailed, covering all edge cases — idempotent disarm (already
  disarmed), partial state (some cameras failed), multi-partition scenario with ASCII diagram
  showing Camera C in partitions P1 and P2: refcount=2 → arm P1 → refcount=1 → arm P2 →
  refcount=0 → detection restored.
- **Troubleshooting section**: Short, ~5 common problems:
  - "NVR not connecting" → check IP/port, self-signed cert acceptance
  - "Webhooks not firing" → check ALERT_WEBHOOK_URL env var
  - "Arm not restoring detection" → camera may belong to another disarmed partition (refcount)
  - "Auto-rearm didn't fire" → check LOG_LEVEL=DEBUG, verify scheduled_rearm_at in DB
  - "Migration fails on startup" → check DATABASE_URL format

### Structured JSON Logging
- **Access log**: Every HTTP request logged at INFO — fields: method, path, status_code,
  duration_ms, request_id. Via FastAPI middleware.
- **Arm/disarm logging**:
  - INFO: start event `{component: 'partition', event: 'disarm_start', partition_id, cameras_count}`
  - INFO: completion `{event: 'disarm_complete', cameras_disarmed, errors_count, duration_ms}`
  - DEBUG: per-camera ISAPI call detail `{event: 'isapi_call', camera_id, detection_type, status}`
- **Component field values**: `'http'` (middleware), `'partition'` (arm/disarm/CRUD),
  `'isapi'` (ISAPI client calls), `'scheduler'` (APScheduler jobs), `'nvr'` (health checks)
- **Default LOG_LEVEL**: `INFO` if env var not set
- **Password safety**: NVR passwords filtered from all log output (NVR-06 — already locked)
- **Implementation**: Python stdlib `logging` with a custom `JsonFormatter` — no extra
  dependency. `request_id` injected via FastAPI middleware into context var (or structlog
  contextvars if stdlib proves awkward).

### Graceful Shutdown
- **Timeout**: 30 seconds fixed — covers worst case (ISAPI connection 5s + read 10s + retry
  10s + buffer). Docker Compose `stop_grace_period: 35s` to give 5s extra beyond app timeout.
- **On timeout expiry**: Log WARNING `{event: 'shutdown_forced', active_isapi_calls: N}` then
  exit. Never block indefinitely.
- **APScheduler**: `scheduler.shutdown(wait=True)` — jobs in progress (auto-rearm) complete
  before exit. Uses same 30s budget shared with ISAPI drain.
- **Mechanism**: Track in-flight ISAPI calls with an asyncio counter/event in the lifespan
  context. On SIGTERM: stop accepting new requests (uvicorn handles), wait for counter to
  reach zero or timeout.

### Claude's Discretion
- Exact Python base image (python:3.12-slim recommended — asyncpg has musl libc issues
  with alpine)
- Multi-stage build layer ordering and caching strategy
- Docker health check command and interval
- `request_id` generation (UUID4 vs nanoid vs X-Request-ID header passthrough)
- Whether to use `structlog` or stdlib `logging` with custom formatter
- Postgres volume name and network name in docker-compose.yml

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/main.py` lifespan — graceful shutdown hook goes here (already has startup/teardown
  pattern for migrations and engine disposal)
- `app/core/config.py` — already loads env vars; add `LOG_LEVEL: str = "INFO"` here
- `app/isapi/client.py` — all ISAPI calls go through here; in-flight tracking counter
  attaches at this layer
- `pyproject.toml` — `uvicorn[standard]` already included; no new deps needed for logging

### Established Patterns
- Lifespan context manager in `app/main.py` — add scheduler init, in-flight counter init,
  and graceful drain logic here
- `app/core/` module — add `logging.py` (JsonFormatter, setup_logging()) here
- All existing routes use `APIResponse[T]` — structured logging wraps around this, doesn't
  change response shape

### Integration Points
- `app/main.py` — add logging setup call at app startup (before first request)
- FastAPI middleware — add request_id injection + access log middleware
- `Dockerfile` → `docker-compose.yml` references the app image; build context is project root
- `.env.example` → documents all vars already in `app/core/config.py`

</code_context>

<specifics>
## Specific Ideas

- `docker compose up` with zero manual steps is the primary success criterion — the
  Dockerfile must handle everything (install deps, run migrations on startup via lifespan,
  no separate migration step)
- README should be readable by a security integrator who has never used FastAPI or Python,
  not just by developers

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 06-infrastructure*
*Context gathered: 2026-03-10*
