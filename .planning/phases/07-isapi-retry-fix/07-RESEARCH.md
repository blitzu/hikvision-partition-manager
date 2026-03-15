# Phase 7: ISAPI Retry Fix & Deployment Hardening - Research

**Researched:** 2026-03-15
**Domain:** Python/httpx retry patterns, FastAPI settings injection, APScheduler interval config
**Confidence:** HIGH

## Summary

This is a mechanical gap-closure phase. All three changes are small, surgical patches to code that already exists and works — the patterns are already demonstrated elsewhere in the codebase. No new libraries, no new architecture, no ambiguity in approach.

The retry pattern for `get_device_info` and `get_camera_channels` is a verbatim copy of what `get_detection_config` and `put_detection_config` already do: inline `try/except httpx.TimeoutException` within the open `async with httpx.AsyncClient()` block. The settings import for `BASE_URL` is already used elsewhere in `app/ui/routes.py`'s dependency chain — it just needs to be imported directly into the routes module. The `IntervalTrigger` change in `app/main.py` is a one-line substitution.

The test approach (Claude's discretion) follows the established pattern in `tests/test_isapi_client.py` exactly: mock `httpx.AsyncClient`, use `side_effect` lists to inject `TimeoutException` on the first call and a successful response on the second, assert `call_count == 2`. Same pattern applies symmetrically to `get_device_info` and `get_camera_channels`.

**Primary recommendation:** Copy the retry block from `get_detection_config` into `get_device_info` and `get_camera_channels` verbatim. Replace four `http://localhost:8000` strings with `f"{settings.BASE_URL}"` (or bare `settings.BASE_URL` where no interpolation is needed). Change `IntervalTrigger(minutes=5)` to `IntervalTrigger(seconds=settings.POLL_INTERVAL_SECONDS)`. Add four parallel unit tests mirroring the existing retry tests.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**ISAPI Retry Pattern**
- Add the same inline try/except retry pattern to `get_device_info()` and `get_camera_channels()`, matching `get_detection_config()` and `put_detection_config()` exactly
- One retry on `httpx.TimeoutException` only — non-timeout errors (4xx, 5xx) pass through immediately without retry
- Use the same `async with httpx.AsyncClient()` context — retry reuses the same client instance (pattern already established in Phase 2)
- On double timeout: `TimeoutException` propagates to the caller as-is — no wrapping, no custom error type
- Callers already handle `TimeoutException` correctly (NVR pre-check sets state=error on timeout)

**BASE_URL Fix**
- Replace all 4 hardcoded `http://localhost:8000` strings in `app/ui/routes.py` with `settings.BASE_URL`
- Import `settings` from `app.core.config` — already used elsewhere in the codebase
- `settings.BASE_URL` already exists with default `"http://localhost:8000"` — no config changes needed

**POLL_INTERVAL_SECONDS Wiring**
- Change `stuck_disarmed_monitor` scheduler from `IntervalTrigger(minutes=5)` to `IntervalTrigger(seconds=settings.POLL_INTERVAL_SECONDS)`
- Direct pass-through in seconds — no unit conversion; config is already in seconds
- NVR health check stays hardcoded at `IntervalTrigger(seconds=60)` — fixed operational interval, not user-configurable
- No new config vars needed

### Claude's Discretion
- Test coverage approach for the new retry behavior on `get_device_info` and `get_camera_channels`
- Whether to update `.env.example` comments to clarify `POLL_INTERVAL_SECONDS` units

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ISAPI-03 | On timeout, system retries once before marking camera/NVR as error | Retry pattern verified in `get_detection_config`/`put_detection_config`; gap confirmed — `get_device_info` and `get_camera_channels` currently have no retry. Direct copy of existing inline try/except block closes the gap. |
</phase_requirements>

---

## Standard Stack

All libraries are already installed. No new dependencies.

### Core (already in use)
| Library | Version | Purpose | Role in this phase |
|---------|---------|---------|---------------------|
| httpx | >=0.27 | Async HTTP client | `httpx.TimeoutException` is the only exception class caught for retry |
| pydantic-settings | >=2.0 | Settings from env | `settings.BASE_URL` and `settings.POLL_INTERVAL_SECONDS` already defined |
| APScheduler | >=4.0.0a6 | In-process scheduler | `IntervalTrigger` already imported; change `minutes=5` to `seconds=settings.POLL_INTERVAL_SECONDS` |

### No New Dependencies
This phase adds zero new packages.

## Architecture Patterns

### Retry Pattern (copy verbatim from `get_detection_config`)

The existing pattern at `app/isapi/client.py` lines 69-76:

```python
# Source: app/isapi/client.py — get_detection_config()
async with _track_inflight():
    async with httpx.AsyncClient(**self._client_kwargs) as client:
        try:
            resp = await client.get(url)
        except httpx.TimeoutException:
            resp = await client.get(url)
        resp.raise_for_status()
        return self._parse_xml(resp.text)
```

Apply identically to `get_device_info`:
- The `url` is `f"{self.base_url}/ISAPI/System/deviceInfo"`
- Return value is `self._parse_xml(resp.text)` (dict)
- The existing `_track_inflight()` context manager wrapper stays unchanged

Apply identically to `get_camera_channels`:
- The `url` is `f"{self.base_url}/ISAPI/System/Video/inputs/channels"`
- Return value is `self._parse_channel_list(resp.text)` (list)
- The existing `_track_inflight()` context manager wrapper stays unchanged

### settings Import in routes.py

`settings` is NOT currently imported in `app/ui/routes.py`. The module imports `app.core.config` indirectly through `app.partitions.service` — but `settings` itself must be imported directly:

```python
# Add to existing imports in app/ui/routes.py
from app.core.config import settings
```

Then the four replacements:

| Line | Before | After |
|------|--------|-------|
| 485 | `f"http://localhost:8000/api/nvrs/{nvr_id}/cameras/sync"` | `f"{settings.BASE_URL}/api/nvrs/{nvr_id}/cameras/sync"` |
| 540 | `f"http://localhost:8000/api/nvrs/{nvr_id}/test"` | `f"{settings.BASE_URL}/api/nvrs/{nvr_id}/test"` |
| 571 | `"http://localhost:8000/api/locations"` | `f"{settings.BASE_URL}/api/locations"` |
| 668 | `f"http://localhost:8000/api/locations/{location_id}/nvrs"` | `f"{settings.BASE_URL}/api/locations/{location_id}/nvrs"` |

### IntervalTrigger Change in main.py

Current `app/main.py` line 91-92:
```python
# Current — hardcoded 5 minutes
await scheduler.add_schedule(
    stuck_disarmed_monitor,
    IntervalTrigger(minutes=5),
    id="stuck_disarmed_monitor",
    conflict_policy=ConflictPolicy.replace,
)
```

After fix:
```python
# Fixed — reads from settings (unit: seconds, default 300)
await scheduler.add_schedule(
    stuck_disarmed_monitor,
    IntervalTrigger(seconds=settings.POLL_INTERVAL_SECONDS),
    id="stuck_disarmed_monitor",
    conflict_policy=ConflictPolicy.replace,
)
```

`settings` is already imported at `app/main.py` line 21.

### Anti-Patterns to Avoid

- **Decorator-based retry:** Locked out. The codebase uses inline try/except only. Do not introduce `tenacity`, `backoff`, or a wrapper function.
- **Retry on all exceptions:** Only `httpx.TimeoutException` is caught. `HTTPStatusError` (4xx/5xx) must propagate immediately.
- **Wrapping the exception:** On double timeout, re-raise the raw `httpx.TimeoutException` — no custom error type.
- **Unit conversion confusion:** `POLL_INTERVAL_SECONDS` is already in seconds. Pass it to `IntervalTrigger(seconds=...)`, not `minutes=...`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Retry on timeout | Custom retry decorator or loop | Inline try/except (already in codebase) | Established pattern; simpler semantics for single-retry |
| Config value access | `os.getenv("POLL_INTERVAL_SECONDS")` | `settings.POLL_INTERVAL_SECONDS` | Pydantic-settings handles parsing, defaults, env file |
| Self-call base URL | Hardcoded string | `settings.BASE_URL` | Deployment environments differ; hardcode breaks docker/non-localhost |

## Common Pitfalls

### Pitfall 1: `settings` not imported in routes.py
**What goes wrong:** `NameError: name 'settings' is not defined` at runtime when any of the four UI proxy endpoints is called.
**Why it happens:** `settings` is available in `app.core.config` but is not currently imported in `app/ui/routes.py` (confirmed by reading the file — no `settings` import present).
**How to avoid:** Add `from app.core.config import settings` to the imports block in `app/ui/routes.py`.
**Warning signs:** `NameError` in test or at first UI form submission.

### Pitfall 2: Using `minutes=` instead of `seconds=` for POLL_INTERVAL_SECONDS
**What goes wrong:** Monitor fires every `300 minutes` (5 hours) instead of every `300 seconds` (5 minutes) at default config.
**Why it happens:** `IntervalTrigger` accepts both `minutes=` and `seconds=` kwargs; easy to pass a seconds-valued int to `minutes=`.
**How to avoid:** The config field is named `POLL_INTERVAL_SECONDS` — match the kwarg name. Use `IntervalTrigger(seconds=settings.POLL_INTERVAL_SECONDS)`.
**Warning signs:** No visible test failure (timing is not unit-tested); runtime-only issue.

### Pitfall 3: Applying retry to `raise_for_status()` errors
**What goes wrong:** 401/404/500 responses get retried, masking real NVR-side errors and doubling latency.
**Why it happens:** Putting the retry block around the whole `try` including `raise_for_status()`.
**How to avoid:** Only catch `httpx.TimeoutException` — the exception raised during network I/O, before `raise_for_status()` is called. `raise_for_status()` stays outside the try/except.

### Pitfall 4: Forgetting the `locations_by_id` key in nvrs.html template context (not this phase)
**What goes wrong:** This is a pre-existing template dependency, not introduced by this phase. Keep it untouched.
**How to avoid:** Do not touch routes other than the four localhost substitutions.

## Code Examples

### Retry block for `get_device_info` (final form)

```python
# Source: modeled on app/isapi/client.py get_detection_config()
async def get_device_info(self) -> dict:
    """GET /ISAPI/System/deviceInfo — returns parsed device info dict."""
    async with _track_inflight():
        async with httpx.AsyncClient(**self._client_kwargs) as client:
            try:
                resp = await client.get(f"{self.base_url}/ISAPI/System/deviceInfo")
            except httpx.TimeoutException:
                resp = await client.get(f"{self.base_url}/ISAPI/System/deviceInfo")
            resp.raise_for_status()
            return self._parse_xml(resp.text)
```

### Retry block for `get_camera_channels` (final form)

```python
# Source: modeled on app/isapi/client.py get_detection_config()
async def get_camera_channels(self) -> list[dict]:
    """GET /ISAPI/System/Video/inputs/channels — returns list of channel dicts."""
    async with _track_inflight():
        async with httpx.AsyncClient(**self._client_kwargs) as client:
            try:
                resp = await client.get(
                    f"{self.base_url}/ISAPI/System/Video/inputs/channels"
                )
            except httpx.TimeoutException:
                resp = await client.get(
                    f"{self.base_url}/ISAPI/System/Video/inputs/channels"
                )
            resp.raise_for_status()
            return self._parse_channel_list(resp.text)
```

### Unit test pattern for retry (mirrors existing tests)

```python
# Source: modeled on tests/test_isapi_client.py — test_get_detection_config_timeout_retries_once_then_raises
async def test_get_device_info_timeout_retries_once_then_raises(client: ISAPIClient) -> None:
    mock_http_client = AsyncMock()
    mock_http_client.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
    mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_http_client.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_http_client):
        with pytest.raises(httpx.TimeoutException):
            await client.get_device_info()

    assert mock_http_client.get.call_count == 2


async def test_get_device_info_first_timeout_second_success(client: ISAPIClient) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "<DeviceInfo><model>DS-7608NI</model></DeviceInfo>"
    mock_response.raise_for_status = MagicMock()

    mock_http_client = AsyncMock()
    mock_http_client.get = AsyncMock(
        side_effect=[httpx.TimeoutException("timeout"), mock_response]
    )
    mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_http_client.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_http_client):
        result = await client.get_device_info()

    assert result == {"model": "DS-7608NI"}
    assert mock_http_client.get.call_count == 2
```

The same pattern applies symmetrically to `get_camera_channels`.

## State of the Art

| Old State | Fixed State | Impact |
|-----------|-------------|--------|
| `get_device_info` — no retry | Retries once on `TimeoutException` | Matches ISAPI-03 spec; consistent with all other ISAPI methods |
| `get_camera_channels` — no retry | Retries once on `TimeoutException` | Matches ISAPI-03 spec |
| `http://localhost:8000` hardcoded x4 in routes.py | `settings.BASE_URL` | UI self-calls work in any deployment (docker, reverse proxy, non-standard port) |
| `IntervalTrigger(minutes=5)` in main.py | `IntervalTrigger(seconds=settings.POLL_INTERVAL_SECONDS)` | `POLL_INTERVAL_SECONDS` env var now actually drives the monitor interval |

## Open Questions

1. **`.env.example` comment update (Claude's discretion)**
   - What we know: `.env.example` line 14 already has a comment: `# Interval in seconds for the stuck-disarmed monitor job (default: 300 = 5 minutes)`. This is accurate and clear.
   - What's unclear: Whether to add a note that this config is now actively wired (it was previously inert).
   - Recommendation: Update the comment to add `# Wired to stuck_disarmed_monitor scheduler interval` to signal it's no longer inert. Low-cost, useful for operators.

2. **Test file location (Claude's discretion)**
   - What we know: Retry tests for `get_detection_config`/`put_detection_config` live in `tests/test_isapi_client.py`. New tests for `get_device_info` and `get_camera_channels` belong in the same file.
   - Recommendation: Append new test functions to `tests/test_isapi_client.py` — no new test file needed.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio 0.23 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` — `asyncio_mode = "auto"` |
| Quick run command | `pytest tests/test_isapi_client.py -x` |
| Full suite command | `pytest tests/ -x` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ISAPI-03 | `get_device_info` retries once on `TimeoutException`, raises on double timeout | unit | `pytest tests/test_isapi_client.py -x -k "device_info"` | ❌ Wave 0 |
| ISAPI-03 | `get_device_info` first timeout then success returns result | unit | `pytest tests/test_isapi_client.py -x -k "device_info"` | ❌ Wave 0 |
| ISAPI-03 | `get_camera_channels` retries once on `TimeoutException`, raises on double timeout | unit | `pytest tests/test_isapi_client.py -x -k "camera_channels"` | ❌ Wave 0 |
| ISAPI-03 | `get_camera_channels` first timeout then success returns result | unit | `pytest tests/test_isapi_client.py -x -k "camera_channels"` | ❌ Wave 0 |
| BASE_URL | UI routes use `settings.BASE_URL` not hardcoded string | unit/smoke | `pytest tests/test_isapi_client.py -x` (indirect: config-level) | Manual verify |
| POLL | `IntervalTrigger` uses `settings.POLL_INTERVAL_SECONDS` | smoke | `pytest tests/ -x` (startup integration) | Manual verify |

Note: BASE_URL and POLL changes are mechanical substitutions. Automated unit tests for them would require mocking `httpx.AsyncClient` inside UI routes (already done in `tests/test_ui.py`). A code-review check (grep for `localhost:8000` returning zero hits) is sufficient for BASE_URL. The IntervalTrigger change is verified by inspection.

### Sampling Rate
- **Per task commit:** `pytest tests/test_isapi_client.py -x`
- **Per wave merge:** `pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] New test functions in `tests/test_isapi_client.py` — covers ISAPI-03 for `get_device_info` (double-timeout raises, first-timeout-then-success)
- [ ] New test functions in `tests/test_isapi_client.py` — covers ISAPI-03 for `get_camera_channels` (double-timeout raises, first-timeout-then-success)

No new test files needed. No framework install needed. Existing `conftest.py` and fixtures are sufficient.

## Sources

### Primary (HIGH confidence)
- Direct code inspection: `app/isapi/client.py` — retry pattern verified in `get_detection_config` and `put_detection_config`
- Direct code inspection: `app/core/config.py` — `settings.BASE_URL` and `settings.POLL_INTERVAL_SECONDS` confirmed present with correct types
- Direct code inspection: `app/main.py` lines 90-95 — `IntervalTrigger(minutes=5)` confirmed; `settings` import confirmed at line 21
- Direct code inspection: `app/ui/routes.py` lines 485, 540, 571, 668 — four hardcoded `http://localhost:8000` strings confirmed; `settings` NOT imported
- Direct code inspection: `tests/test_isapi_client.py` — retry test pattern confirmed; establishes exact mock structure to reuse
- Direct code inspection: `.env.example` — `POLL_INTERVAL_SECONDS` comment already accurate; minor wording update optional

### Secondary (MEDIUM confidence)
- None needed — all findings are direct code inspection at HIGH confidence

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new libraries; everything verified by direct file reads
- Architecture: HIGH — retry pattern is copy-paste from existing working code; all file locations and line numbers confirmed
- Pitfalls: HIGH — derived from actual code state (missing `settings` import is a confirmed gap, not hypothetical)

**Research date:** 2026-03-15
**Valid until:** 2026-04-15 (stable codebase; no fast-moving dependencies)
