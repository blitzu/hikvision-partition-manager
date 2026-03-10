# Phase 1: Foundation - Context

**Gathered:** 2026-03-10
**Status:** Ready for planning

<domain>
## Phase Boundary

The data layer exists and operators can manage locations, NVRs, and cameras through a working API. Covers: all 9 database tables with migrations, location/NVR/camera CRUD endpoints, NVR password encryption at rest, camera sync from NVR via ISAPI, and a connectivity test endpoint. No partition logic, no admin UI, no scheduled jobs — those are later phases.

</domain>

<decisions>
## Implementation Decisions

### Project Layout
- Feature/domain modules: `app/locations/`, `app/nvrs/`, `app/cameras/` — each with `routes.py`, `models.py`, `schemas.py`
- App entrypoint: `app/main.py` (creates the FastAPI app, includes routers, sets up lifespan events)
- Shared infrastructure in `app/core/`: `config.py` (env vars), `database.py` (connection pool), `crypto.py` (encryption)
- Tests: Claude's discretion — use a conventional layout for this type of service

### Database Access Layer
- SQLAlchemy ORM with async sessions (`AsyncSession` + `asyncpg` driver)
- Native PostgreSQL types in ORM: `ARRAY(UUID)` for `disarmed_by_partitions`, `JSONB` for detection snapshots
- All DB access is async/non-blocking to support concurrent ISAPI + DB calls in later phases

### Migration Tooling
- Alembic for schema migrations
- Location: `alembic/` at project root (`alembic/env.py`, `alembic/versions/`)
- Auto-run on service startup via `alembic upgrade head` in FastAPI lifespan event — satisfies zero-manual-steps requirement

### Phase 1 API Shape
- Standard response envelope `{ success, data, error }` used from Phase 1 onward — no retrofit needed in Phase 3
- Implement a minimal ISAPI HTTP client in Phase 1 for: GET `/ISAPI/System/deviceInfo` (connectivity test) and GET channel list (camera sync); Phase 2 extends this with Digest auth, retry logic, and disarm/arm operations
- Connectivity test failures return HTTP 200 with `{ success: false, data: null, error: "<message>" }` — consistent envelope, no mixed HTTP error codes for downstream failures

### Claude's Discretion
- Tests directory layout (conventional Python layout for this service type)
- Exact Pydantic schema structure for each domain
- Connection pool sizing defaults

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- None — greenfield project. All patterns are established in Phase 1.

### Established Patterns
- All patterns originate here: response envelope, SQLAlchemy async session factory, Alembic env, httpx client wrapper, domain module structure

### Integration Points
- `app/core/database.py` → session dependency injected into all route handlers
- `app/core/crypto.py` → used by NVR CRUD to encrypt/decrypt passwords
- `app/core/config.py` → loads `DATABASE_URL`, `ENCRYPTION_KEY`, `BASE_URL` from environment
- Minimal ISAPI client in Phase 1 → extended in Phase 2 (not replaced)

</code_context>

<specifics>
## Specific Ideas

- No specific references — open to standard FastAPI project conventions for the layout
- The minimal ISAPI client built in Phase 1 should be designed as an extension point so Phase 2 can add Digest auth, TLS options, retry logic without restructuring

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 01-foundation*
*Context gathered: 2026-03-10*
