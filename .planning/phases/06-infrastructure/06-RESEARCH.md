# Phase 6: Infrastructure - Research

**Researched:** 2026-03-11
**Domain:** Docker Compose deployment, structured logging, graceful shutdown, Python asyncio
**Confidence:** HIGH

## Summary

This phase ships the service: write the Dockerfile + docker-compose.yml so `docker compose up` starts everything with zero manual steps, implement structured JSON logging via a stdlib `JsonFormatter`, wire graceful shutdown for in-flight ISAPI calls, audit all DB queries for parameterization, and write README.md + .env.example.

No new features are introduced. All implementation attaches to patterns already established in the codebase: the lifespan context manager in `app/main.py`, the settings class in `app/core/config.py`, and the ISAPI client in `app/isapi/client.py`.

The work splits cleanly into three areas: (1) container packaging (Dockerfile + compose), (2) observability (structured logging + access log middleware + graceful shutdown), and (3) documentation (.env.example + README.md + INFRA-07 SQL audit). All seven requirements are fully within the existing tech stack — no new dependencies are required.

**Primary recommendation:** Implement in wave order: container first (enables local verify), then observability (logging + shutdown), then documentation. Each wave is independently testable.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**README Audience & Structure:**
- Two audiences, separate sections: Quick Start (developer cloning for local run) + Integration Guide (operator connecting an existing VMS).
- VMS Integration Guide: curl examples for POST disarm, POST arm, GET state, GET dashboard. Plus a narrative workflow: "When an alarm fires: 1. POST /disarm with disarmed_by 2. Monitor state via GET /state 3. POST /arm when event clears".
- Refcount explanation: Detailed, covering all edge cases — idempotent disarm (already disarmed), partial state (some cameras failed), multi-partition scenario with ASCII diagram showing Camera C in partitions P1 and P2: refcount=2 → arm P1 → refcount=1 → arm P2 → refcount=0 → detection restored.
- Troubleshooting section: Short, ~5 common problems: "NVR not connecting", "Webhooks not firing", "Arm not restoring detection", "Auto-rearm didn't fire", "Migration fails on startup".

**Structured JSON Logging:**
- Access log: Every HTTP request logged at INFO — fields: method, path, status_code, duration_ms, request_id. Via FastAPI middleware.
- Arm/disarm logging: INFO start/completion events; DEBUG per-camera ISAPI call detail.
- Component field values: `'http'`, `'partition'`, `'isapi'`, `'scheduler'`, `'nvr'`.
- Default LOG_LEVEL: `INFO` if env var not set (already set in `app/core/config.py`).
- Password safety: NVR passwords filtered from all log output (NVR-06 — already locked).
- Implementation: Python stdlib `logging` with a custom `JsonFormatter` — no extra dependency. `request_id` injected via FastAPI middleware into context var (or structlog contextvars if stdlib proves awkward).

**Graceful Shutdown:**
- Timeout: 30 seconds fixed — covers worst case (ISAPI connection 5s + read 10s + retry 10s + buffer). Docker Compose `stop_grace_period: 35s`.
- On timeout expiry: Log WARNING `{event: 'shutdown_forced', active_isapi_calls: N}` then exit. Never block indefinitely.
- APScheduler: `scheduler.shutdown(wait=True)` — APScheduler 4.x uses `async with scheduler:` context; jobs in progress complete before exit. Uses same 30s budget.
- Mechanism: Track in-flight ISAPI calls with an asyncio counter/event in the lifespan context. On SIGTERM: stop accepting new requests (uvicorn handles), wait for counter to reach zero or timeout.

### Claude's Discretion
- Exact Python base image (python:3.12-slim recommended — asyncpg has musl libc issues with alpine)
- Multi-stage build layer ordering and caching strategy
- Docker health check command and interval
- `request_id` generation (UUID4 vs nanoid vs X-Request-ID header passthrough)
- Whether to use `structlog` or stdlib `logging` with custom formatter
- Postgres volume name and network name in docker-compose.yml

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| INFRA-01 | docker-compose.yml with app + postgres services, volume for data persistence, health checks; starts with zero manual steps | Docker Compose v2 patterns, postgres official image, health check syntax |
| INFRA-02 | Multi-stage Dockerfile, non-root user, minimal image | python:3.12-slim base, multi-stage build, useradd/USER patterns |
| INFRA-03 | .env.example with all required variables: DATABASE_URL, ENCRYPTION_KEY, ALERT_WEBHOOK_URL, POLL_INTERVAL_SECONDS, LOG_LEVEL, BASE_URL | Existing `app/core/config.py` Settings class documents all vars |
| INFRA-04 | README.md with 3-step setup, env vars table, API curl examples, VMS integration guide, refcount logic explanation | Locked in CONTEXT.md — content is fully specified |
| INFRA-05 | Structured JSON logging with timestamp, level, request_id, component fields | Python stdlib `logging.Formatter`, FastAPI middleware, contextvars |
| INFRA-06 | Graceful shutdown: complete in-flight ISAPI calls before exit | asyncio.Event/counter pattern, FastAPI lifespan, uvicorn SIGTERM |
| INFRA-07 | All database queries parameterized (no string interpolation) | SQLAlchemy ORM always parameterizes; audit is a code review task |
</phase_requirements>

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| python:3.12-slim | 3.12 | Docker base image | Debian-based; asyncpg wheels available; smaller than full python image |
| docker compose | v2 (plugin) | Container orchestration | Replaces legacy docker-compose v1; `docker compose up` syntax |
| postgres | 16 | Database service in compose | LTS release, well-supported asyncpg driver |
| uvicorn | already in pyproject.toml | ASGI server entrypoint | Already used; `--host 0.0.0.0` needed inside container |
| Python stdlib `logging` | 3.12 | Structured JSON logging | No new dep; `JsonFormatter` is a well-known pattern |
| Python `contextvars` | 3.12 | request_id propagation | stdlib; works with asyncio without threading issues |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `uuid` (stdlib) | 3.12 | request_id generation | Simpler than nanoid; UUID4 is sufficient for correlation |
| `json` (stdlib) | 3.12 | Serialize log records | Part of JsonFormatter implementation |
| `time` (stdlib) | 3.12 | duration_ms in access log | `time.monotonic()` for elapsed timing |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| stdlib `logging` + `JsonFormatter` | `structlog` | structlog is cleaner API but adds a dependency; context already decided stdlib preferred |
| UUID4 request_id | X-Request-ID passthrough | Passthrough is better for tracing but adds complexity; UUID4 is simpler and sufficient |
| python:3.12-slim | python:3.12-alpine | Alpine has musl libc; asyncpg requires glibc — use slim |

**Installation:** No new packages. All tools are stdlib or already in `pyproject.toml`.

---

## Architecture Patterns

### Recommended Project Structure (new files for this phase)

```
/                             # project root
├── Dockerfile                # multi-stage build
├── docker-compose.yml        # app + postgres + health checks
├── .env.example              # all required vars (update existing)
├── README.md                 # Quick Start + VMS Integration Guide
└── app/
    ├── core/
    │   └── logging.py        # JsonFormatter + setup_logging()
    └── middleware/
        └── logging.py        # RequestIdMiddleware + access log
```

### Pattern 1: Multi-Stage Dockerfile

**What:** Builder stage installs deps; runtime stage copies only installed packages.
**When to use:** Always for production Python images — avoids shipping build tools and source.

```dockerfile
# Stage 1: builder
FROM python:3.12-slim AS builder
WORKDIR /build
COPY pyproject.toml .
COPY app/ app/
RUN pip install --no-cache-dir --prefix=/install .

# Stage 2: runtime
FROM python:3.12-slim
# Non-root user (UID 1000 is conventional)
RUN useradd --create-home --uid 1000 appuser
WORKDIR /app
# Copy installed packages from builder
COPY --from=builder /install /usr/local
# Copy application source
COPY --chown=appuser:appuser . .
USER appuser
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Key considerations:
- `alembic.ini` uses `script_location = %(here)s/alembic` — the alembic directory must be present in the runtime image (COPY . .)
- `--host 0.0.0.0` is required; default 127.0.0.1 is unreachable from outside the container
- `--no-cache-dir` in pip reduces image size

### Pattern 2: Docker Compose with Health Checks and Dependency

**What:** Postgres service with health check; app service depends on postgres being healthy.
**When to use:** `docker compose up` zero-step requirement — app must not start before postgres accepts connections.

```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_USER: appuser
      POSTGRES_PASSWORD: apppassword
      POSTGRES_DB: partitions
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U appuser -d partitions"]
      interval: 5s
      timeout: 5s
      retries: 10

  app:
    build: .
    env_file: .env
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy
    stop_grace_period: 35s   # 30s app timeout + 5s buffer

volumes:
  pgdata:
```

Key: `condition: service_healthy` (not just `depends_on: db`) is critical for zero-manual-step startup. Without it, the app starts before postgres is accepting connections and migrations fail.

Note on DATABASE_URL in compose context: The `.env` file uses `localhost:5432` (for local dev). In compose, the hostname is the service name `db`. The `.env.example` should show the compose URL; the actual `.env` used by compose should override. Best pattern: set `DATABASE_URL` in compose `environment:` block pointing to `db:5432`, overriding the `.env` file value for compose usage — or document clearly in README.

### Pattern 3: stdlib JsonFormatter

**What:** Custom `logging.Formatter` that emits JSON lines. Added to `app/core/logging.py`.
**When to use:** All log output in production; configured once at app startup.

```python
# app/core/logging.py
import json
import logging
import time


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        # Get request_id from context var if set
        from app.middleware.logging import request_id_var
        rid = request_id_var.get(None)

        log_obj = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S.%fZ"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": rid,
        }
        # Merge any extra fields passed to logger.info(..., extra={...})
        for key, val in record.__dict__.items():
            if key not in logging.LogRecord.__dict__ and key not in log_obj:
                log_obj[key] = val
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_obj)


def setup_logging(log_level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=log_level.upper(), handlers=[handler], force=True)
```

Call `setup_logging(settings.LOG_LEVEL)` at the top of `app/main.py` (before FastAPI app instantiation).

### Pattern 4: request_id Middleware + Access Log

**What:** FastAPI middleware generates a request_id per request, injects into context var, logs access at INFO on response.
**When to use:** All HTTP requests.

```python
# app/middleware/logging.py
import time
import uuid
import logging
from contextvars import ContextVar
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

request_id_var: ContextVar[str] = ContextVar("request_id", default="")
logger = logging.getLogger("http")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        rid = str(uuid.uuid4())
        token = request_id_var.set(rid)
        start = time.monotonic()
        response = await call_next(request)
        duration_ms = round((time.monotonic() - start) * 1000, 1)
        logger.info(
            "request",
            extra={
                "component": "http",
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "request_id": rid,
            },
        )
        request_id_var.reset(token)
        return response
```

Register in `app/main.py`:
```python
from app.middleware.logging import RequestLoggingMiddleware
app.add_middleware(RequestLoggingMiddleware)
```

### Pattern 5: In-Flight ISAPI Tracking + Graceful Shutdown

**What:** asyncio counter + Event tracks active ISAPI calls. On SIGTERM (lifespan exit), wait for counter to reach zero or 30s timeout.
**When to use:** Lifespan context in `app/main.py`; wraps all ISAPI calls in `app/isapi/client.py`.

```python
# app/core/inflight.py
import asyncio

_count = 0
_event = asyncio.Event()
_event.set()  # starts "idle"


def increment():
    global _count
    _count += 1
    _event.clear()


def decrement():
    global _count
    _count -= 1
    if _count == 0:
        _event.set()


async def wait_drain(timeout: float = 30.0) -> int:
    """Wait for all in-flight calls to complete. Returns remaining count."""
    try:
        await asyncio.wait_for(_event.wait(), timeout=timeout)
        return 0
    except asyncio.TimeoutError:
        return _count
```

In `app/isapi/client.py`, wrap each ISAPI call:
```python
from app.core.inflight import increment, decrement

async def get_detection_config(self, ...) -> str:
    increment()
    try:
        # ... existing implementation ...
    finally:
        decrement()
```

In `app/main.py` lifespan (after `yield`):
```python
import logging
from app.core.inflight import wait_drain

logger = logging.getLogger(__name__)

# ... after yield (shutdown begins) ...
remaining = await wait_drain(timeout=30.0)
if remaining > 0:
    logger.warning(
        "Shutdown forced with active ISAPI calls",
        extra={"event": "shutdown_forced", "active_isapi_calls": remaining, "component": "http"},
    )
```

APScheduler graceful shutdown is already handled by `async with scheduler:` — the context manager waits for running jobs to complete when exiting.

### Anti-Patterns to Avoid

- **`--host 127.0.0.1` in Dockerfile CMD:** Container cannot be reached. Always use `0.0.0.0`.
- **`depends_on: db` without `condition: service_healthy`:** App starts before postgres is ready; migrations fail; zero-manual-step requirement broken.
- **`python:3.12-alpine`:** asyncpg requires glibc; musl libc causes build failures without complex workarounds.
- **Module-level asyncio globals for inflight counter:** `asyncio.Event()` created at import time may bind to the wrong event loop in Python 3.10+. Initialize inside the lifespan or use `asyncio.get_event_loop()` carefully. Simpler: use a mutable dict `{"count": 0}` + asyncio.Event created in lifespan, passed via app.state.
- **Logging setup after first import:** Many libraries grab loggers at import time. `setup_logging()` must be called before app = FastAPI(...) and before first router import.
- **f-string SQL:** INFRA-07 prohibits `f"SELECT ... WHERE id = {user_input}"`. SQLAlchemy ORM `.where(Model.id == value)` is always parameterized. The audit is about finding any raw `text()` with interpolated values.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Postgres readiness in compose | Custom wait-for-it.sh script | `pg_isready` health check + `condition: service_healthy` | pg_isready is built into the postgres image; health checks are compose-native |
| JSON log formatting | Manual dict serialization per logger.info call | `JsonFormatter` in basicConfig handler | One formatter handles all log output uniformly |
| Shutdown signal handling | Custom SIGTERM handler with signal.signal() | FastAPI lifespan `yield` (uvicorn sends SIGTERM → lifespan cleanup runs) | uvicorn already translates SIGTERM into lifespan exit; don't fight it |
| DB connection retry on startup | Polling loop in lifespan | `depends_on: condition: service_healthy` in compose | Compose handles the retry; app code stays clean |

**Key insight:** The compose health check + `condition: service_healthy` is the only reliable zero-manual-step pattern. Scripts like `wait-for-it.sh` are fragile and require extra tooling in the image.

---

## Common Pitfalls

### Pitfall 1: DATABASE_URL hostname mismatch between local dev and compose

**What goes wrong:** `.env` has `localhost:5432`. When running via `docker compose up`, the app container cannot reach `localhost:5432` because postgres is in the `db` container. Migrations fail at startup.
**Why it happens:** `.env` is designed for local dev (postgres running on host). Compose uses service names as DNS hostnames.
**How to avoid:** Override `DATABASE_URL` in the compose `environment:` block: `DATABASE_URL=postgresql+asyncpg://appuser:apppassword@db:5432/partitions`. The compose env block takes precedence over `.env` file values.
**Warning signs:** App exits immediately with `asyncpg.exceptions.ConnectionRefusedError` on `docker compose up`.

### Pitfall 2: asyncio.Event() created at module level in wrong event loop

**What goes wrong:** `asyncio.Event()` created at module import time in Python 3.10+ raises `DeprecationWarning` or binds to a closed event loop.
**Why it happens:** Module-level globals are initialized before the asyncio event loop starts.
**How to avoid:** Create `asyncio.Event()` objects inside the FastAPI lifespan (or use `app.state` to store them). The inflight tracking object can be instantiated in the lifespan and passed to the ISAPI client via dependency injection or `app.state`.
**Warning signs:** `DeprecationWarning: There is no current event loop` on startup.

### Pitfall 3: Multi-stage build fails because alembic/ directory is missing at runtime

**What goes wrong:** `alembic.ini` points to `script_location = %(here)s/alembic`. If `COPY` in the runtime stage doesn't include `alembic/`, migrations fail at startup.
**Why it happens:** Multi-stage builds only copy what you explicitly include. `COPY app/ app/` misses `alembic/` and `alembic.ini`.
**How to avoid:** Use `COPY --chown=appuser:appuser . .` in the runtime stage to copy everything, including `alembic/` and `alembic.ini`. Or copy them explicitly.
**Warning signs:** `FileNotFoundError: [Errno 2] No such file or directory: '/app/alembic'` in container logs.

### Pitfall 4: Non-root user cannot write to mounted volumes or read .env

**What goes wrong:** Files owned by root cannot be read/written by `appuser` (UID 1000).
**Why it happens:** `useradd` creates the user but doesn't change ownership of files already in the image.
**How to avoid:** Use `COPY --chown=appuser:appuser . .` rather than `COPY . .` + `chown`. Avoid writing to the filesystem at runtime (use volumes for postgres only; app is stateless).
**Warning signs:** `PermissionError` reading `.env` or writing logs.

### Pitfall 5: Graceful shutdown counter race condition

**What goes wrong:** `decrement()` is called before the response is fully sent; OR increment/decrement are not balanced (e.g., exception skips decrement).
**Why it happens:** Missing `try/finally` around the decrement call.
**How to avoid:** Always wrap ISAPI call body with `try/finally: decrement()`. Use a context manager:
```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def track_inflight():
    increment()
    try:
        yield
    finally:
        decrement()
```
**Warning signs:** Counter never reaches 0; shutdown hangs until the 30s timeout.

### Pitfall 6: INFRA-07 — SQLAlchemy `text()` with f-strings

**What goes wrong:** Developer uses `await db.execute(text(f"SELECT ... WHERE id = {some_id}"))` thinking SQLAlchemy handles parameterization. But `text()` with f-strings is raw SQL with interpolation — SQL injection risk.
**Why it happens:** `text()` is for raw SQL; it requires `:param` style parameters.
**How to avoid:** Either use ORM query builders (`.where(Model.id == some_id)`) or `text("... WHERE id = :id").bindparams(id=some_id)`. Audit all `text()` calls in the codebase.
**Warning signs:** `f"` inside a `text()` call.

---

## Code Examples

### JsonFormatter with extra fields

```python
# Source: Python stdlib logging docs + project convention
import json
import logging


class JsonFormatter(logging.Formatter):
    SKIP_ATTRS = frozenset(logging.LogRecord.__dict__) | {
        "message", "asctime", "args", "msg"
    }

    def format(self, record: logging.LogRecord) -> str:
        from app.middleware.logging import request_id_var
        log_obj = {
            "timestamp": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_var.get(""),
        }
        for key, val in record.__dict__.items():
            if key not in self.SKIP_ATTRS:
                log_obj[key] = val
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_obj, default=str)
```

### Structured log calls in partition service

```python
import logging
logger = logging.getLogger(__name__)

# INFO: disarm start
logger.info("disarm_start", extra={
    "component": "partition",
    "event": "disarm_start",
    "partition_id": str(partition_id),
    "cameras_count": len(cameras),
})

# INFO: disarm complete
logger.info("disarm_complete", extra={
    "component": "partition",
    "event": "disarm_complete",
    "cameras_disarmed": cameras_disarmed,
    "errors_count": errors_count,
    "duration_ms": round((time.monotonic() - start) * 1000, 1),
})

# DEBUG: per-camera ISAPI detail
logger.debug("isapi_call", extra={
    "component": "isapi",
    "event": "isapi_call",
    "camera_id": str(camera_id),
    "detection_type": detection_type,
    "status": "ok",
})
```

### Password filter in logging

```python
# NVR-06: passwords must never appear in logs
# Current pattern: ISAPIClient receives decrypted password but never logs it.
# Audit: ensure no logger.debug() or logger.info() calls include `password` fields.
# Defensive option: add a logging.Filter subclass that scrubs any record
# containing "password" in extra fields.

class PasswordFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # Remove any 'password' key from extra fields
        record.__dict__.pop("password", None)
        # Also scrub from message
        if "password" in record.getMessage().lower():
            record.msg = "[REDACTED - password in log message]"
        return True
```

### SQLAlchemy parameterization audit pattern

```python
# CORRECT — ORM always parameterizes
stmt = select(Partition).where(Partition.id == partition_id)

# CORRECT — text() with bindparams
from sqlalchemy import text
stmt = text("SELECT * FROM partitions WHERE id = :id").bindparams(id=partition_id)

# WRONG — DO NOT DO THIS (INFRA-07 violation)
stmt = text(f"SELECT * FROM partitions WHERE id = {partition_id}")
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `docker-compose` (v1 CLI) | `docker compose` (v2 plugin) | Docker Desktop 3.x / Engine 20.10 | Syntax change: hyphen → space |
| `HEALTHCHECK` in Dockerfile | `healthcheck:` in compose | Always available in compose | Compose health check gives `condition: service_healthy` |
| `logging.basicConfig()` once | `logging.basicConfig(..., force=True)` | Python 3.8 | `force=True` needed when libraries configure logging before you do |
| Module-level asyncio.Event() | Event created inside async context | Python 3.10 deprecation | Must create inside running loop |

**Deprecated/outdated:**
- `docker-compose` (v1, separate binary): replaced by `docker compose` plugin — use v2 syntax
- `POLL_INTERVAL_SECONDS` env var: required by INFRA-03 but not currently in `app/core/config.py` Settings — needs to be added

---

## Open Questions

1. **POLL_INTERVAL_SECONDS env var**
   - What we know: INFRA-03 requires it in .env.example; it is not currently defined in `app/core/config.py`
   - What's unclear: Is it used anywhere in the codebase? The stuck-disarmed monitor interval is hardcoded to 5 minutes in `app/main.py`.
   - Recommendation: Add `POLL_INTERVAL_SECONDS: int = 300` to Settings and use it as the interval for `stuck_disarmed_monitor`. Otherwise document it as "reserved for future use" in .env.example with a comment.

2. **inflight counter initialization timing**
   - What we know: `asyncio.Event()` must not be created at module level in Python 3.10+
   - What's unclear: Best injection pattern — `app.state` vs. passing to ISAPIClient constructor vs. global with lazy init
   - Recommendation: Use `app.state.inflight_event = asyncio.Event()` set in lifespan startup, and pass via a module-level container initialized inside lifespan. This is the pattern FastAPI recommends for shared resources.

3. **DATABASE_URL in compose vs .env**
   - What we know: `.env` uses `localhost:5432`; compose needs `db:5432`
   - What's unclear: Whether to document "edit .env before compose up" or override in compose YAML
   - Recommendation: Override in `docker-compose.yml` environment block (`DATABASE_URL=postgresql+asyncpg://appuser:apppassword@db:5432/partitions`) so `docker compose up` works without editing .env.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio 0.23.x |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `pytest tests/test_infra.py -x -q` |
| Full suite command | `pytest tests/ -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INFRA-01 | `docker compose up` starts with zero manual steps | manual smoke | `docker compose up -d && sleep 10 && curl -f http://localhost:8000/api/dashboard` | N/A |
| INFRA-02 | Dockerfile builds, non-root user, multi-stage | manual build | `docker build -t hpm . && docker run --rm hpm whoami` | N/A |
| INFRA-03 | .env.example has all required vars | unit | `pytest tests/test_infra.py::test_env_example_has_all_vars -x` | Wave 0 |
| INFRA-04 | README.md exists with required sections | unit | `pytest tests/test_infra.py::test_readme_has_required_sections -x` | Wave 0 |
| INFRA-05 | JSON logging emits structured fields | unit | `pytest tests/test_infra.py::test_json_formatter -x` | Wave 0 |
| INFRA-05 | Access log middleware logs request fields | unit | `pytest tests/test_infra.py::test_access_log_middleware -x` | Wave 0 |
| INFRA-06 | Graceful shutdown waits for in-flight calls | unit | `pytest tests/test_infra.py::test_graceful_shutdown_drain -x` | Wave 0 |
| INFRA-07 | No f-string SQL interpolation in codebase | static audit | `grep -rn "text(f" app/ || true` | N/A (code review) |

### Sampling Rate
- **Per task commit:** `pytest tests/test_infra.py -x -q`
- **Per wave merge:** `pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_infra.py` — covers INFRA-03, INFRA-04, INFRA-05, INFRA-06
- [ ] `app/core/logging.py` — JsonFormatter + setup_logging()
- [ ] `app/middleware/__init__.py` — package init
- [ ] `app/middleware/logging.py` — RequestLoggingMiddleware + request_id_var
- [ ] `app/core/inflight.py` — in-flight ISAPI counter

---

## Sources

### Primary (HIGH confidence)
- Python stdlib `logging` docs (3.12) — Formatter, LogRecord, basicConfig, force=True
- Python stdlib `contextvars` docs (3.12) — ContextVar, asyncio integration
- FastAPI docs — lifespan, middleware (BaseHTTPMiddleware), app.state
- Docker Compose reference — healthcheck syntax, depends_on condition: service_healthy, stop_grace_period
- SQLAlchemy 2.0 docs — ORM query parameterization, text() bindparams

### Secondary (MEDIUM confidence)
- Docker multi-stage build docs — builder/runtime pattern, COPY --from, --chown flag
- postgres:16 Docker Hub — pg_isready command, healthcheck pattern

### Tertiary (LOW confidence)
- asyncio.Event module-level creation deprecation — observed in Python 3.10 changelog

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries are stdlib or already in pyproject.toml; no new dependencies
- Architecture: HIGH — Docker multi-stage and compose patterns are well-documented and stable
- Pitfalls: HIGH — DATABASE_URL hostname issue and alembic path issue are project-specific and verified by reading the existing codebase

**Research date:** 2026-03-11
**Valid until:** 2026-06-11 (stable patterns; Docker Compose and Python logging APIs are very stable)
