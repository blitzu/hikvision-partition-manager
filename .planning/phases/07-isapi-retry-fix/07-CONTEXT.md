# Phase 7: ISAPI Retry Fix & Deployment Hardening - Context

**Gathered:** 2026-03-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Gap-closure phase fixing three specific code issues discovered in the v1.0 audit:
1. Add retry-on-timeout to `get_device_info()` and `get_camera_channels()` in `ISAPIClient`
2. Replace 4 hardcoded `http://localhost:8000` strings in `app/ui/routes.py` with `settings.BASE_URL`
3. Wire `settings.POLL_INTERVAL_SECONDS` into the `stuck_disarmed_monitor` scheduler interval

No new capabilities — only correcting gaps where implemented behavior diverges from spec.

</domain>

<decisions>
## Implementation Decisions

### ISAPI Retry Pattern
- Add the same inline try/except retry pattern to `get_device_info()` and `get_camera_channels()`, matching `get_detection_config()` and `put_detection_config()` exactly
- One retry on `httpx.TimeoutException` only — non-timeout errors (4xx, 5xx) pass through immediately without retry
- Use the same `async with httpx.AsyncClient()` context — retry reuses the same client instance (pattern already established in Phase 2)
- On double timeout: `TimeoutException` propagates to the caller as-is — no wrapping, no custom error type
- Callers already handle `TimeoutException` correctly (NVR pre-check sets state=error on timeout)

### BASE_URL Fix
- Replace all 4 hardcoded `http://localhost:8000` strings in `app/ui/routes.py` with `settings.BASE_URL`
- Import `settings` from `app.core.config` — already used elsewhere in the codebase
- `settings.BASE_URL` already exists with default `"http://localhost:8000"` — no config changes needed

### POLL_INTERVAL_SECONDS Wiring
- Change `stuck_disarmed_monitor` scheduler from `IntervalTrigger(minutes=5)` to `IntervalTrigger(seconds=settings.POLL_INTERVAL_SECONDS)`
- Direct pass-through in seconds — no unit conversion; config is already in seconds
- NVR health check stays hardcoded at `IntervalTrigger(seconds=60)` — fixed operational interval, not user-configurable
- No new config vars needed

### Claude's Discretion
- Test coverage approach for the new retry behavior on `get_device_info` and `get_camera_channels`
- Whether to update `.env.example` comments to clarify `POLL_INTERVAL_SECONDS` units

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/isapi/client.py`: `get_detection_config()` and `put_detection_config()` have the exact retry pattern to copy into `get_device_info()` and `get_camera_channels()`
- `app/core/config.py`: `settings.BASE_URL` (default `"http://localhost:8000"`) and `settings.POLL_INTERVAL_SECONDS` (default 300) already defined
- `app/main.py`: `add_schedule` calls for both monitor jobs are side-by-side — minimal diff to update

### Established Patterns
- Retry: inline `try/except httpx.TimeoutException` within the open `async with httpx.AsyncClient()` block — do NOT use a decorator or wrapper
- Settings import: `from app.core.config import settings` — already used in routes and main
- `_track_inflight()` context manager wraps all ISAPI calls — retry stays inside this context

### Integration Points
- `app/ui/routes.py` line ~485, ~540, ~571, ~668: hardcoded `http://localhost:8000` → `settings.BASE_URL`
- `app/main.py` line ~92: `IntervalTrigger(minutes=5)` → `IntervalTrigger(seconds=settings.POLL_INTERVAL_SECONDS)`

</code_context>

<specifics>
## Specific Ideas

No specific requirements — changes are mechanical patches matching existing patterns.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 07-isapi-retry-fix*
*Context gathered: 2026-03-15*
