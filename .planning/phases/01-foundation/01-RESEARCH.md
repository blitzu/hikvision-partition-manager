# Phase 1: Foundation - Research

**Researched:** 2026-03-10
**Domain:** FastAPI + SQLAlchemy 2.0 async + PostgreSQL 16 + Alembic + httpx + cryptography
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Feature/domain modules: `app/locations/`, `app/nvrs/`, `app/cameras/` — each with `routes.py`, `models.py`, `schemas.py`
- App entrypoint: `app/main.py` (creates the FastAPI app, includes routers, sets up lifespan events)
- Shared infrastructure in `app/core/`: `config.py` (env vars), `database.py` (connection pool), `crypto.py` (encryption)
- SQLAlchemy ORM with async sessions (`AsyncSession` + `asyncpg` driver)
- Native PostgreSQL types in ORM: `ARRAY(UUID)` for `disarmed_by_partitions`, `JSONB` for detection snapshots
- All DB access is async/non-blocking
- Alembic for schema migrations, located at project root (`alembic/` dir)
- Auto-run on service startup via `alembic upgrade head` in FastAPI lifespan event
- Standard response envelope `{ success, data, error }` used from Phase 1 onward
- Implement a minimal ISAPI HTTP client in Phase 1 for: GET `/ISAPI/System/deviceInfo` and GET channel list (camera sync)
- Connectivity test failures return HTTP 200 with `{ success: false, data: null, error: "<message>" }` — consistent envelope

### Claude's Discretion
- Tests directory layout (conventional Python layout for this service type)
- Exact Pydantic schema structure for each domain
- Connection pool sizing defaults

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DATA-01 | System stores locations with name and timezone | PostgreSQL table + SQLAlchemy model; `zoneinfo` for timezone validation |
| DATA-02 | System stores NVR devices linked to a location, with encrypted password, IP, port, model, status | Fernet encryption in `crypto.py`; SQLAlchemy relationship to locations |
| DATA-03 | System stores cameras linked to NVR with channel number and enabled flag; (nvr_id, channel_no) unique | `UniqueConstraint` in SQLAlchemy; upsert pattern via `insert().on_conflict_do_update()` |
| DATA-04 | System stores virtual partitions with name, description, auto_rearm_minutes, alert_if_disarmed_minutes | Simple table; defined in Phase 1 for schema completeness, no CRUD needed yet |
| DATA-05 | System stores partition-camera membership (many-to-many) | Association table; schema only in Phase 1 |
| DATA-06 | System stores partition_state per partition: state enum, last_changed_at, last_changed_by, scheduled_rearm_at, error_detail | SA enum type; schema only in Phase 1 |
| DATA-07 | System stores camera_detection_snapshot per camera per partition: full JSONB of ISAPI response, taken_at | `JSONB` from `sqlalchemy.dialects.postgresql`; schema only in Phase 1 |
| DATA-08 | System stores camera_disarm_refcount per camera: array of partition_ids, generated count column | `ARRAY(UUID)` + `GeneratedColumn` (or computed via trigger); schema only in Phase 1 |
| DATA-09 | System stores partition_audit_log: partition_id, action, performed_by, metadata JSONB, created_at | JSONB + schema only in Phase 1 |
| NVR-01 | Operator can create a location (name, timezone) | POST /api/locations; Pydantic validation of timezone string |
| NVR-02 | Operator can add an NVR device to a location; password stored encrypted | Fernet encrypt on write, never decrypt into response |
| NVR-03 | Operator can test NVR connectivity; returns deviceInfo on success | httpx.AsyncClient + DigestAuth; HTTP 200 envelope always |
| NVR-04 | Operator can sync cameras from NVR via ISAPI channel list; upserts by (nvr_id, channel_no) | PostgreSQL upsert; `lxml` or `xml.etree.ElementTree` for XML parse |
| NVR-05 | System updates nvr_devices.last_seen_at and status on every successful ISAPI contact | DB write after every successful httpx call |
| NVR-06 | NVR passwords never written to logs or API responses | Field excluded from Pydantic response schema; no logging of password field |
</phase_requirements>

---

## Summary

Phase 1 establishes the complete data layer (all nine tables) and a working CRUD API for locations, NVRs, and cameras, including NVR connectivity testing and camera sync from live ISAPI. The tech stack is Python 3.12 + FastAPI + SQLAlchemy 2.0 async + asyncpg + Alembic, which is a well-documented and stable combination as of early 2026.

The two highest-risk areas are: (1) running Alembic migrations inside FastAPI's async lifespan — this requires `asyncio.to_thread` or the Alembic async template's `run_sync` wrapper, and (2) NVR password security — Fernet (AES-128-CBC + HMAC-SHA256) from the `cryptography` library satisfies the "encrypted at rest, never in response" requirement, but the Pydantic response schema must explicitly exclude the `password_encrypted` field. Everything else follows well-trodden patterns.

The minimal ISAPI client built here is the extension point for Phase 2. It must be designed as a class or module that Phase 2 can subclass/extend with Digest auth retry logic without restructuring. Phase 1 ISAPI calls only need `httpx.AsyncClient(verify=False, auth=httpx.DigestAuth(...))` for GET deviceInfo and GET channel list.

**Primary recommendation:** Follow SQLAlchemy 2.0 declarative mapping with `Mapped[T]` type annotations throughout. Use `async_sessionmaker(expire_on_commit=False)` as the session factory. Run Alembic via `asyncio.to_thread` in the FastAPI lifespan startup. Use `insert().on_conflict_do_update()` for the camera upsert. Exclude password fields from Pydantic response models by omitting the field entirely (not using `exclude={"password"}`).

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| fastapi | >=0.115 | HTTP framework, dependency injection, OpenAPI | Project-specified; async-native |
| sqlalchemy | >=2.0 | ORM with async support | Project-specified; required for `AsyncSession` + ARRAY/JSONB types |
| asyncpg | >=0.29 | PostgreSQL async driver | Project-specified; fastest Python PG driver |
| alembic | >=1.13 | Schema migrations | Project-specified; `alembic init -t async` for async env |
| pydantic | v2 (ships with FastAPI 0.100+) | Request/response validation | Ships with FastAPI; v2 required for `model_config` |
| httpx | >=0.27 | ISAPI HTTP client | Project-specified; `DigestAuth` support built-in |
| cryptography | >=42.0 | Fernet encryption for NVR passwords | Project-specified; `Fernet` is simplest correct option |
| uvicorn | >=0.30 | ASGI server | Standard FastAPI deployment |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| python-dotenv | >=1.0 | Load `.env` file for local dev | Development; Pydantic Settings handles prod |
| pydantic-settings | >=2.0 | Typed env var loading | `app/core/config.py` — replaces manual `os.getenv` |
| lxml or stdlib xml.etree | stdlib or lxml>=5.0 | XML parsing for ISAPI responses | `xml.etree.ElementTree` sufficient for Phase 1; lxml for Phase 2 performance |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Fernet (AES-128) | AES-256-GCM via `cryptography` primitives | AES-128 is secure enough; Fernet is simpler and audit-friendly |
| asyncpg | psycopg3 async | asyncpg is faster and more battle-tested with SQLAlchemy async |
| stdlib xml.etree | lxml | lxml faster but extra dependency; stdlib sufficient for Phase 1 |

**Installation:**
```bash
pip install fastapi uvicorn[standard] sqlalchemy[asyncio] asyncpg alembic \
            pydantic-settings python-dotenv httpx cryptography lxml
```

---

## Architecture Patterns

### Recommended Project Structure
```
hikvision-partition-manager/
├── alembic/
│   ├── env.py               # async Alembic env (run_sync wrapper)
│   ├── script.py.mako
│   └── versions/            # migration files
├── app/
│   ├── main.py              # FastAPI app, lifespan, router includes
│   ├── core/
│   │   ├── config.py        # pydantic-settings BaseSettings
│   │   ├── database.py      # engine, async_sessionmaker, get_db dependency
│   │   └── crypto.py        # Fernet encrypt/decrypt helpers
│   ├── locations/
│   │   ├── models.py        # SQLAlchemy Location model
│   │   ├── schemas.py       # Pydantic LocationCreate, LocationRead
│   │   └── routes.py        # APIRouter for /api/locations
│   ├── nvrs/
│   │   ├── models.py        # NVRDevice model
│   │   ├── schemas.py       # NVRCreate (has password), NVRRead (no password)
│   │   └── routes.py        # APIRouter for /api/nvrs and /api/locations/{id}/nvrs
│   ├── cameras/
│   │   ├── models.py        # Camera model
│   │   ├── schemas.py       # CameraRead
│   │   └── routes.py        # /api/nvrs/{id}/cameras/sync
│   └── isapi/
│       └── client.py        # ISAPIClient class — Phase 1 minimal, Phase 2 extends
├── tests/
│   ├── conftest.py          # engine, session, client fixtures
│   ├── test_locations.py
│   ├── test_nvrs.py
│   ├── test_cameras.py
│   └── test_isapi_client.py
├── alembic.ini
├── pyproject.toml
└── .env.example
```

Note: `app/isapi/client.py` is a separate module (not inside `nvrs/`) so Phase 2 can extend it without touching the NVR CRUD files.

### Pattern 1: Async Session Factory with get_db Dependency
**What:** `async_sessionmaker` creates sessions; route handlers receive sessions via `Depends(get_db)`.
**When to use:** Every route that touches the database.
```python
# app/core/database.py
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from collections.abc import AsyncGenerator
from app.core.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_pre_ping=True,   # detect stale connections
    echo=False,
)

async_session_factory = async_sessionmaker(
    engine,
    expire_on_commit=False,   # CRITICAL: prevents lazy-load errors after commit
    class_=AsyncSession,
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session
```

### Pattern 2: SQLAlchemy 2.0 Declarative ORM with Mapped[] Annotations
**What:** Use `DeclarativeBase`, `Mapped[T]`, `mapped_column()` throughout — not legacy Column/relationship.
**When to use:** Every model file.
```python
# app/locations/models.py
import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class Location(Base):
    __tablename__ = "locations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
```

### Pattern 3: PostgreSQL ARRAY(UUID) and JSONB
**What:** Use dialect-specific types from `sqlalchemy.dialects.postgresql`.
**When to use:** `disarmed_by_partitions` column and snapshot/metadata JSONB columns.
```python
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy import Column

# In camera_disarm_refcount model:
disarmed_by_partitions: Mapped[list[uuid.UUID]] = mapped_column(
    ARRAY(UUID(as_uuid=True)), nullable=False, default=list
)

# In camera_detection_snapshot model:
snapshot_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
```

### Pattern 4: Alembic Async Migration in Lifespan
**What:** Run `alembic upgrade head` at startup using thread pool (avoids blocking async loop).
**When to use:** FastAPI lifespan startup.
```python
# app/main.py
import asyncio
from contextlib import asynccontextmanager
from alembic.config import Config
from alembic import command

def run_migrations():
    """Runs in a thread — alembic command.upgrade is sync."""
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")

@asynccontextmanager
async def lifespan(app: FastAPI):
    await asyncio.to_thread(run_migrations)
    yield
    await engine.dispose()

app = FastAPI(lifespan=lifespan)
```
Note: `asyncio.to_thread` is the recommended workaround for the known issue where running `command.upgrade` directly in async context can fail (alembic #1606, confirmed in 2024-2025 discussions).

### Pattern 5: Alembic env.py for Async Engine
**What:** Initialize with the async template and configure target_metadata.
```python
# alembic/env.py (initialized via: alembic init -t async alembic)
from app.core.database import Base
# Import all models so autogenerate detects them:
from app.locations.models import Location
from app.nvrs.models import NVRDevice
from app.cameras.models import Camera
# ... all other models

target_metadata = Base.metadata
```

### Pattern 6: Camera Upsert (nvr_id, channel_no unique)
**What:** PostgreSQL `INSERT ... ON CONFLICT DO UPDATE` via SQLAlchemy Core.
**When to use:** Camera sync endpoint — must never create duplicates.
```python
from sqlalchemy.dialects.postgresql import insert

async def upsert_camera(session: AsyncSession, data: dict) -> Camera:
    stmt = insert(Camera).values(**data)
    stmt = stmt.on_conflict_do_update(
        index_elements=["nvr_id", "channel_no"],
        set_={
            "name": stmt.excluded.name,
            "enabled": stmt.excluded.enabled,
            "updated_at": func.now(),
        },
    )
    await session.execute(stmt)
    await session.commit()
```

### Pattern 7: Fernet Encryption in crypto.py
**What:** Encrypt NVR password on create, never expose raw password in any response or log.
```python
# app/core/crypto.py
from cryptography.fernet import Fernet
from app.core.config import settings

_fernet = Fernet(settings.ENCRYPTION_KEY.encode())

def encrypt_password(plaintext: str) -> str:
    return _fernet.encrypt(plaintext.encode()).decode()

def decrypt_password(ciphertext: str) -> str:
    return _fernet.decrypt(ciphertext.encode()).decode()
```
The `ENCRYPTION_KEY` must be a URL-safe base64-encoded 32-byte key (`Fernet.generate_key()` produces one).

### Pattern 8: NVR Response Schema Excludes Password
**What:** Pydantic response model has no `password` or `password_encrypted` field — field simply does not exist.
**When to use:** Every NVR-returning endpoint.
```python
# app/nvrs/schemas.py
class NVRCreate(BaseModel):
    name: str
    ip_address: str
    port: int = 8000
    username: str
    password: str  # plaintext on create only

class NVRRead(BaseModel):
    id: uuid.UUID
    name: str
    ip_address: str
    port: int
    username: str
    location_id: uuid.UUID
    status: str
    last_seen_at: datetime | None
    # NO password field here

    model_config = ConfigDict(from_attributes=True)
```

### Pattern 9: Minimal ISAPI Client (Extension Point for Phase 2)
**What:** A class that encapsulates httpx.AsyncClient; Phase 2 adds retry, full Digest challenge handling.
**When to use:** Phase 1 builds the skeleton; Phase 2 extends.
```python
# app/isapi/client.py
import httpx

class ISAPIClient:
    """Minimal ISAPI client for Phase 1. Phase 2 extends with retry + full Digest."""

    def __init__(self, host: str, port: int, username: str, password: str):
        self.base_url = f"http://{host}:{port}"
        self._auth = httpx.DigestAuth(username, password)
        self._client_kwargs = {
            "auth": self._auth,
            "verify": False,          # NVRs use self-signed certs
            "timeout": httpx.Timeout(connect=5.0, read=10.0),
        }

    async def get_device_info(self) -> dict:
        async with httpx.AsyncClient(**self._client_kwargs) as client:
            resp = await client.get(f"{self.base_url}/ISAPI/System/deviceInfo")
            resp.raise_for_status()
            return self._parse_xml(resp.text)

    async def get_camera_channels(self) -> list[dict]:
        async with httpx.AsyncClient(**self._client_kwargs) as client:
            resp = await client.get(
                f"{self.base_url}/ISAPI/System/Video/inputs/channels"
            )
            resp.raise_for_status()
            return self._parse_channel_list(resp.text)

    def _parse_xml(self, xml_text: str) -> dict:
        import xml.etree.ElementTree as ET
        root = ET.fromstring(xml_text)
        # Strip XML namespace for simple access
        ns = {"h": "http://www.hikvision.com/ver20/XMLSchema"}
        # Return dict of tag -> text
        return {child.tag.split("}")[-1]: child.text for child in root}

    def _parse_channel_list(self, xml_text: str) -> list[dict]:
        import xml.etree.ElementTree as ET
        root = ET.fromstring(xml_text)
        channels = []
        for ch in root.iter():
            if ch.tag.endswith("VideoInputChannel"):
                channels.append({
                    "channel_no": int(ch.find(".//{*}id").text),
                    "name": (ch.find(".//{*}name") or ch).text,
                })
        return channels
```

Note: Hikvision NVRs use `http://` by default on port 8000; some configurations use HTTPS on 443. Phase 1 can start with HTTP only; HTTPS with `verify=False` works identically with httpx.

### Pattern 10: Response Envelope
**What:** All endpoints return `{ success: bool, data: any, error: str | null }`.
```python
# app/core/schemas.py
from typing import Generic, TypeVar
from pydantic import BaseModel

T = TypeVar("T")

class APIResponse(BaseModel, Generic[T]):
    success: bool
    data: T | None = None
    error: str | None = None
```

### Anti-Patterns to Avoid
- **`expire_on_commit=True` (the default):** Causes `MissingGreenlet` / DetachedInstanceError when accessing ORM attributes after `await session.commit()`. Always set `expire_on_commit=False`.
- **Awaiting `command.upgrade` directly in async context:** Hangs or raises `AttributeError: context has no attribute 'configure'`. Use `asyncio.to_thread`.
- **Logging `nvr.password` or including it in exception messages:** A formatted error like `f"Failed to connect to {nvr.ip}:{nvr.port} with {nvr.password}"` will appear in structured logs. Never reference password in any string interpolation.
- **Importing models in `routes.py` but not in `alembic/env.py`:** Alembic autogenerate won't detect tables it hasn't seen. Import every model module in `env.py`.
- **Using `Column()` instead of `mapped_column()`:** SQLAlchemy 2.0 type checking only works with the new-style `Mapped[T]` + `mapped_column()` syntax. Old-style `Column()` is deprecated.
- **Creating a new `httpx.AsyncClient` per-request without a context manager:** Leaves connections open. Always use `async with httpx.AsyncClient(...) as client:` or use a shared client with explicit lifecycle management.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Symmetric encryption | Custom AES wrapper | `cryptography.Fernet` | Handles IV generation, HMAC auth, base64 encoding correctly |
| DB migration | Manual `CREATE TABLE` on startup | Alembic | Handles schema diffs, rollback, history |
| Upsert on unique conflict | SELECT then INSERT/UPDATE | `insert().on_conflict_do_update()` | Atomic, race-condition-free |
| XML namespace stripping | Regex on XML strings | `ET.fromstring()` + tag split on `}` | Correct and handles all edge cases |
| Digest auth challenge-response | Manual `WWW-Authenticate` parsing | `httpx.DigestAuth` | Handles nonce, qop, nc, cnonce correctly |
| Env var validation | `os.getenv()` with manual checks | `pydantic-settings BaseSettings` | Type coercion, required field enforcement, `.env` loading |

**Key insight:** Encryption-at-rest and ISAPI authentication are both security-sensitive. Using battle-tested library implementations avoids subtle vulnerabilities from hand-rolled crypto or auth logic.

---

## Common Pitfalls

### Pitfall 1: expire_on_commit and DetachedInstanceError
**What goes wrong:** After `await session.commit()`, accessing `orm_object.id` raises `MissingGreenlet` because SQLAlchemy tries to lazy-load expired attributes.
**Why it happens:** Default `expire_on_commit=True` marks all attributes as expired post-commit; in async context there is no implicit IO allowed.
**How to avoid:** Set `expire_on_commit=False` on `async_sessionmaker`. Alternatively `await session.refresh(obj)` immediately after commit.
**Warning signs:** `sqlalchemy.exc.MissingGreenlet` or `DetachedInstanceError` in logs.

### Pitfall 2: Alembic Autogenerate Missing Tables
**What goes wrong:** `alembic revision --autogenerate` generates an empty migration even though models exist.
**Why it happens:** Models not imported in `alembic/env.py` before `target_metadata = Base.metadata`.
**How to avoid:** Add explicit imports of every model module in `env.py`. Import order does not matter; just ensure all modules are loaded.
**Warning signs:** Empty `upgrade()` function in generated migration file.

### Pitfall 3: asyncio.to_thread Alembic Startup
**What goes wrong:** `command.upgrade(cfg, "head")` called directly in `async` lifespan function raises `AttributeError: context has no attribute 'configure'`.
**Why it happens:** Alembic's migration context uses threading.local; async context causes thread-local state to be lost.
**How to avoid:** Wrap the call: `await asyncio.to_thread(run_migrations)` where `run_migrations` is a plain sync function.
**Warning signs:** Error in application startup log mentioning `context.configure`.

### Pitfall 4: Hikvision DigestAuth httpx Known Issue
**What goes wrong:** httpx DigestAuth works for the first request but subsequent requests to the same NVR return 401 Unauthorized.
**Why it happens:** httpx pull/2463 changed how the auth challenge is stored; some Hikvision firmware versions are sensitive to this.
**How to avoid:** Create a new `httpx.AsyncClient` per ISAPI operation (not shared across requests). This is acceptable for Phase 1's low-frequency connectivity tests and sync operations.
**Warning signs:** 401 on second consecutive ISAPI call using same client instance.

### Pitfall 5: ARRAY(UUID) Default
**What goes wrong:** `ARRAY(UUID)` column with `default=[]` causes mutable default shared across all ORM instances.
**Why it happens:** Python mutable default argument anti-pattern.
**How to avoid:** Use `default=list` (not `default=[]`) or `server_default=text("'{}'::uuid[]")`.
**Warning signs:** One camera's `disarmed_by_partitions` array contains partition IDs from another camera object.

### Pitfall 6: NVR Password Leaking via Exception Messages
**What goes wrong:** An exception handler logs `str(exc)` which includes connection details that were formatted with the decrypted password.
**Why it happens:** HTTP client errors from httpx sometimes include the full URL or auth headers in the exception string.
**How to avoid:** Catch `httpx.HTTPError` before stringifying; log only `exc.__class__.__name__` and a sanitized message. Never format the password into any string.
**Warning signs:** Password string appearing in structured log output.

### Pitfall 7: Timezone Validation for DATA-01
**What goes wrong:** Accepting any string for `timezone` column, then failing at runtime when pytz or zoneinfo can't locate it.
**Why it happens:** No validation at the API boundary.
**How to avoid:** Validate in Pydantic schema using `zoneinfo.ZoneInfo(tz_string)` — raises `ZoneInfoNotFoundError` on invalid input, which maps to a 422 response.
**Warning signs:** `ZoneInfoNotFoundError` at partition scheduling time (Phase 4).

---

## Code Examples

### Database engine and session factory
```python
# app/core/database.py
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from collections.abc import AsyncGenerator
from app.core.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,         # postgresql+asyncpg://...
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    echo=settings.DB_ECHO,
)

async_session_factory = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session
```

### pydantic-settings config
```python
# app/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str                    # postgresql+asyncpg://user:pass@host/db
    ENCRYPTION_KEY: str                  # 44-char URL-safe base64 Fernet key
    BASE_URL: str = "http://localhost:8000"
    LOG_LEVEL: str = "INFO"
    DB_ECHO: bool = False

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
```

### Lifespan with migration
```python
# app/main.py
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from alembic.config import Config
from alembic import command
from app.core.database import engine

def _run_migrations() -> None:
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")

@asynccontextmanager
async def lifespan(app: FastAPI):
    await asyncio.to_thread(_run_migrations)
    yield
    await engine.dispose()

app = FastAPI(title="Hikvision Partition Manager", lifespan=lifespan)
```

### ISAPI connectivity test route with envelope
```python
# app/nvrs/routes.py (excerpt)
@router.get("/{nvr_id}/test")
async def test_connectivity(
    nvr_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> APIResponse[dict]:
    nvr = await db.get(NVRDevice, nvr_id)
    if not nvr:
        return APIResponse(success=False, error="NVR not found")

    password = decrypt_password(nvr.password_encrypted)
    client = ISAPIClient(nvr.ip_address, nvr.port, nvr.username, password)
    try:
        device_info = await client.get_device_info()
        # NVR-05: update last_seen_at and status on success
        nvr.last_seen_at = datetime.now(UTC)
        nvr.status = "online"
        await db.commit()
        return APIResponse(success=True, data=device_info)
    except Exception as exc:
        nvr.status = "offline"
        await db.commit()
        # NVR-03: HTTP 200 + success=false on connectivity failure
        return APIResponse(success=False, data=None, error=f"NVR unreachable: {type(exc).__name__}")
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `Column()` + `relationship()` | `Mapped[T]` + `mapped_column()` | SQLAlchemy 2.0 (2023) | Required for type safety and async correctness |
| `create_engine` + `Session` | `create_async_engine` + `AsyncSession` | SQLAlchemy 1.4+ async (stable in 2.0) | Non-blocking DB access |
| Alembic `alembic init` | `alembic init -t async alembic` | Alembic 1.9+ | env.py uses async engine pattern |
| `@app.on_event("startup")` | `lifespan` context manager | FastAPI 0.93 (2023) | `on_event` is deprecated |
| Pydantic v1 `class Config:` | Pydantic v2 `model_config = ConfigDict(...)` | Pydantic v2 (2023) | Required for `from_attributes=True` |
| `requests` + `HTTPDigestAuth` | `httpx.AsyncClient` + `httpx.DigestAuth` | httpx 0.20+ | Async-native digest auth |

**Deprecated/outdated:**
- `@app.on_event("startup"/"shutdown")`: Replaced by `lifespan`. Do not use.
- `Session` (sync) inside async route handlers: Causes blocking. Do not use.
- Pydantic v1 `orm_mode = True`: Replaced by `model_config = ConfigDict(from_attributes=True)`.

---

## Open Questions

1. **Hikvision channel list endpoint path**
   - What we know: `/ISAPI/System/Video/inputs/channels` is cited in community sources; NVRs with ContentMgmt may also expose `/ISAPI/ContentMgmt/StreamingProxy/channels`
   - What's unclear: Exact path varies by NVR firmware and model; no authoritative public documentation
   - Recommendation: Implement `get_camera_channels()` with the most common path and make the URL path configurable or fallback-able in Phase 1; document in code that path may need adjustment per firmware version. Integration test against real device will confirm.

2. **Generated count column for DATA-08**
   - What we know: PostgreSQL supports `GENERATED ALWAYS AS (cardinality(disarmed_by_partitions)) STORED` computed columns; SQLAlchemy 2.0 supports `Computed()` for generated columns
   - What's unclear: Whether SQLAlchemy `Computed()` works correctly with asyncpg for ARRAY cardinality expressions
   - Recommendation: Define `disarm_count` as a `Computed("cardinality(disarmed_by_partitions)", persisted=True)` column in Alembic migration SQL directly. Verify in migration test.

3. **HTTPS vs HTTP for ISAPI**
   - What we know: Hikvision NVRs default to HTTP on port 8000; HTTPS available on port 443 with self-signed cert; `httpx verify=False` handles both
   - What's unclear: Whether the operator's specific NVR fleet uses HTTP or HTTPS; port is user-configurable in NVR-02
   - Recommendation: `ISAPIClient` should detect scheme from `nvr.port` or store scheme separately. For Phase 1, default to HTTP; allow `https://` via a stored `use_https` boolean on NVRDevice.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio |
| Config file | `pyproject.toml` — `[tool.pytest.ini_options]` |
| Quick run command | `pytest tests/ -x -q` |
| Full suite command | `pytest tests/ -v --tb=short` |

**Required test packages:**
```
pytest>=8.0
pytest-asyncio>=0.23
httpx>=0.27        # AsyncClient for test client
```

**pyproject.toml pytest config:**
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

### Test Infrastructure Needed

**Test database:** A real PostgreSQL instance is required for integration tests (ARRAY, JSONB, and upsert logic cannot be tested with SQLite). Options:
1. Docker Compose service: `docker compose up -d postgres` (preferred for CI)
2. `pytest-postgresql` plugin: spins up a temporary PostgreSQL process per session

**conftest.py core fixtures:**
```python
# tests/conftest.py
import asyncio
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.database import Base, get_db

TEST_DATABASE_URL = "postgresql+asyncpg://test:test@localhost:5432/test_partitions"

@pytest_asyncio.fixture(scope="session")
async def engine():
    eng = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()

@pytest_asyncio.fixture(scope="function")
async def db_session(engine):
    """Each test gets a rolled-back transaction for isolation."""
    async with engine.connect() as conn:
        async with conn.begin():
            session = AsyncSession(bind=conn, expire_on_commit=False)
            yield session
            await session.close()
            await conn.rollback()

@pytest_asyncio.fixture(scope="function")
async def client(db_session):
    """AsyncClient with DB dependency override pointing to test session."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()
```

**Mock ISAPI for unit tests:**
```python
# tests/mocks.py
class MockISAPIClient:
    async def get_device_info(self):
        return {"deviceName": "Test-NVR", "model": "DS-7616NI", "serialNumber": "ABC123"}

    async def get_camera_channels(self):
        return [
            {"channel_no": 1, "name": "Camera 1"},
            {"channel_no": 2, "name": "Camera 2"},
        ]
```

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File |
|--------|----------|-----------|-------------------|------|
| DATA-01 | Location table exists with name + timezone constraints | integration | `pytest tests/test_locations.py -x` | Wave 0 |
| DATA-02 | NVR table has encrypted_password, ip, port, model, status, location FK | integration | `pytest tests/test_nvrs.py::test_nvr_schema -x` | Wave 0 |
| DATA-03 | (nvr_id, channel_no) unique constraint enforced | integration | `pytest tests/test_cameras.py::test_unique_constraint -x` | Wave 0 |
| DATA-04 | partitions table exists with all timer columns | integration | `pytest tests/test_schema.py::test_partitions_table -x` | Wave 0 |
| DATA-05 | partition_cameras association table exists | integration | `pytest tests/test_schema.py::test_partition_cameras_table -x` | Wave 0 |
| DATA-06 | partition_state table with enum column exists | integration | `pytest tests/test_schema.py::test_partition_state_table -x` | Wave 0 |
| DATA-07 | camera_detection_snapshot has JSONB column + unique (camera_id, partition_id) | integration | `pytest tests/test_schema.py::test_snapshot_table -x` | Wave 0 |
| DATA-08 | camera_disarm_refcount has ARRAY(UUID) and computed count column | integration | `pytest tests/test_schema.py::test_refcount_table -x` | Wave 0 |
| DATA-09 | partition_audit_log has JSONB metadata, created_at, partition FK | integration | `pytest tests/test_schema.py::test_audit_table -x` | Wave 0 |
| NVR-01 | POST /api/locations creates location; invalid timezone returns 422 | integration | `pytest tests/test_locations.py -x` | Wave 0 |
| NVR-02 | POST /api/locations/{id}/nvrs stores password encrypted; plaintext not in DB | integration | `pytest tests/test_nvrs.py::test_password_encrypted -x` | Wave 0 |
| NVR-03 | GET /api/nvrs/{id}/test returns 200+success=true on mock success; 200+success=false on exception | unit (mock ISAPI) | `pytest tests/test_nvrs.py::test_connectivity -x` | Wave 0 |
| NVR-04 | GET /api/nvrs/{id}/cameras/sync upserts channels; re-sync doesn't duplicate | integration | `pytest tests/test_cameras.py::test_sync_upsert -x` | Wave 0 |
| NVR-05 | last_seen_at and status updated after successful ISAPI contact | integration | `pytest tests/test_nvrs.py::test_last_seen_updated -x` | Wave 0 |
| NVR-06 | NVR password not in any API response or log output | unit | `pytest tests/test_nvrs.py::test_password_not_in_response -x` | Wave 0 |

### Key Test Scenarios (Success Criteria Verification)

1. **End-to-end create flow** (Success Criterion 1):
   ```
   POST /api/locations -> POST /api/locations/{id}/nvrs -> GET /api/nvrs/{id}/cameras/sync
   Assert: location exists, NVR exists linked to location, cameras created linked to NVR
   ```
   Test type: integration (requires real PostgreSQL; ISAPI mocked)

2. **Password security** (Success Criterion 2):
   - Assert `nvr.password_encrypted != original_password` (encrypted in DB)
   - Assert `GET /api/nvrs/{id}` response body has no field containing plaintext password
   - Assert `GET /api/nvrs/` list response has no password field on any item
   Test type: unit + integration

3. **Camera sync upsert dedup** (Success Criterion 3):
   - Sync same channel list twice
   - Assert `SELECT COUNT(*) FROM cameras WHERE nvr_id = ?` equals channel count (not doubled)
   Test type: integration (requires PostgreSQL for ON CONFLICT DO UPDATE)

4. **Connectivity test responses** (Success Criterion 4):
   - Mock ISAPI returns device info -> assert `{ success: true, data: { deviceName: ..., model: ... } }`
   - Mock ISAPI raises `httpx.ConnectError` -> assert HTTP 200 + `{ success: false, error: "..." }`
   Test type: unit (mock ISAPIClient)

5. **Migration from empty database** (Success Criterion 5):
   - Drop all tables, run `alembic upgrade head`, inspect `information_schema.tables`
   - Assert all 9 table names present with expected columns
   Test type: integration

### Sampling Rate
- **Per task commit:** `pytest tests/ -x -q` (fast, fail-fast)
- **Per wave merge:** `pytest tests/ -v --tb=short` (full output)
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
All test infrastructure is new (greenfield project):
- [ ] `tests/conftest.py` — engine, db_session, client fixtures
- [ ] `tests/mocks.py` — MockISAPIClient
- [ ] `tests/test_schema.py` — DATA-01 through DATA-09 table existence tests
- [ ] `tests/test_locations.py` — NVR-01 location CRUD + timezone validation
- [ ] `tests/test_nvrs.py` — NVR-02, NVR-03, NVR-05, NVR-06
- [ ] `tests/test_cameras.py` — NVR-04 sync + upsert dedup
- [ ] Framework install: `pip install pytest pytest-asyncio httpx`
- [ ] Test PostgreSQL service in docker-compose.yml or `.env.test` pointing to a test DB

---

## Sources

### Primary (HIGH confidence)
- SQLAlchemy 2.0 official docs (docs.sqlalchemy.org/en/20) — async engine, ARRAY, JSONB, Mapped[], mapped_column, Computed
- httpx official docs (python-httpx.org) — DigestAuth, AsyncClient, verify=False, Timeout
- cryptography.io official docs — Fernet symmetric encryption, key format
- FastAPI official docs (fastapi.tiangolo.com) — lifespan, Depends, async tests

### Secondary (MEDIUM confidence)
- [Berk Karaal: Setup FastAPI + Async SQLAlchemy 2 + Alembic + PostgreSQL + Docker (2024)](https://berkkaraal.com/blog/2024/09/19/setup-fastapi-project-with-async-sqlalchemy-2-alembic-postgresql-and-docker/) — async Alembic env.py pattern, docker compose migration command
- [Praciano: FastAPI and async SQLAlchemy 2.0 with pytest done right](https://praciano.com.br/fastapi-and-async-sqlalchemy-20-with-pytest-done-right.html) — conftest.py session fixtures, asyncio_mode=auto
- [CORE27: Transactional Unit Tests with Pytest and Async SQLAlchemy](https://www.core27.co/post/transactional-unit-tests-with-pytest-and-async-sqlalchemy) — SAVEPOINT rollback pattern
- [FastAPI official: Async Tests](https://fastapi.tiangolo.com/advanced/async-tests/) — AsyncClient + ASGITransport

### Tertiary (LOW confidence — flag for validation)
- Community reports of httpx DigestAuth issue with Hikvision intercom firmware (httpx/discussions/2549) — affects some firmware versions; mitigation is per-request client instances
- Hikvision ISAPI channel list endpoint path `/ISAPI/System/Video/inputs/channels` — from community reverse engineering, not official public docs; verify against real device

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all core libraries are project-specified; versions verified via PyPI/official docs as of 2026-03
- Architecture: HIGH — FastAPI + SQLAlchemy 2.0 async patterns are well-established and verified via multiple authoritative sources
- ISAPI client: MEDIUM — httpx DigestAuth confirmed working; specific Hikvision endpoint paths are community-verified, not from official docs
- Pitfalls: HIGH — expire_on_commit and Alembic async issues are widely documented and confirmed via official issue trackers
- Test patterns: HIGH — pytest-asyncio auto mode + dependency override pattern is the current standard

**Research date:** 2026-03-10
**Valid until:** 2026-06-01 (stable stack; re-verify if upgrading to SQLAlchemy 2.1 or FastAPI 1.0)
