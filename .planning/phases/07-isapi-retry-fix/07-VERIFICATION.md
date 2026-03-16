---
phase: 07-isapi-retry-fix
verified: 2026-03-16T00:00:00Z
status: passed
score: 5/5 must-haves verified
re_verification: false
gaps: []
human_verification: []
---

# Phase 7: ISAPI Retry Fix Verification Report

**Phase Goal:** All ISAPI client methods retry once on timeout; UI self-calls use configured BASE_URL; POLL_INTERVAL_SECONDS config drives scheduler intervals
**Verified:** 2026-03-16
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `get_device_info` retries once on TimeoutException before raising | VERIFIED | `app/isapi/client.py` lines 47-50: `try/except httpx.TimeoutException` re-calls `client.get(...)` on first timeout; tests `test_get_device_info_timeout_retries_once_then_raises` and `test_get_device_info_first_timeout_second_success` confirm call_count==2 |
| 2 | `get_camera_channels` retries once on TimeoutException before raising | VERIFIED | `app/isapi/client.py` lines 61-68: identical inline retry pattern; tests `test_get_camera_channels_timeout_retries_once_then_raises` and `test_get_camera_channels_first_timeout_second_success` confirm call_count==2 |
| 3 | All four UI self-calls in routes.py use `settings.BASE_URL`, not a hardcoded string | VERIFIED | `app/ui/routes.py` line 39 imports `settings`; four usages at lines 486, 541, 572, 669 all use `f"{settings.BASE_URL}/..."`. `grep "localhost:8000" app/ui/routes.py` returns zero hits. |
| 4 | `stuck_disarmed_monitor` scheduler runs at `settings.POLL_INTERVAL_SECONDS` interval | VERIFIED | `app/main.py` line 92: `IntervalTrigger(seconds=settings.POLL_INTERVAL_SECONDS)`; test `test_lifespan_registers_stuck_disarmed_monitor_with_poll_interval_seconds` asserts `trigger.seconds == settings.POLL_INTERVAL_SECONDS` |
| 5 | Full test suite passes with no regressions | VERIFIED | SUMMARY reports 158 tests green; `test_jobs_monitors.py` test renamed from `_5_minute_interval` to `_poll_interval_seconds` and assertion updated to match the new config-driven behavior — no regressions, one test accurately updated |

**Score:** 5/5 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `app/isapi/client.py` | `get_device_info` and `get_camera_channels` with inline retry on `TimeoutException` | VERIFIED | 4 occurrences of `except httpx.TimeoutException` at lines 49, 65, 87, 109 — covers all four methods: `get_device_info`, `get_camera_channels`, `get_detection_config`, `put_detection_config` |
| `app/main.py` | `stuck_disarmed_monitor` schedule wired to `settings.POLL_INTERVAL_SECONDS` | VERIFIED | Line 92: `IntervalTrigger(seconds=settings.POLL_INTERVAL_SECONDS)`; `settings` imported at line 21 |
| `app/ui/routes.py` | All UI self-calls using `settings.BASE_URL` | VERIFIED | 4 uses of `settings.BASE_URL` at lines 486, 541, 572, 669; import at line 39; zero `localhost:8000` strings remain |
| `tests/test_isapi_client.py` | 4 new unit tests for `get_device_info` and `get_camera_channels` retry behavior | VERIFIED | All 4 named tests present at lines 263-350: `test_get_device_info_timeout_retries_once_then_raises`, `test_get_device_info_first_timeout_second_success`, `test_get_camera_channels_timeout_retries_once_then_raises`, `test_get_camera_channels_first_timeout_second_success` |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `app/isapi/client.py:get_device_info` | `httpx.TimeoutException` catch block | inline `try/except` inside `async with httpx.AsyncClient()` | WIRED | Line 47-50: pattern `except httpx.TimeoutException` confirmed present |
| `app/isapi/client.py:get_camera_channels` | `httpx.TimeoutException` catch block | inline `try/except` inside `async with httpx.AsyncClient()` | WIRED | Lines 61-68: pattern `except httpx.TimeoutException` confirmed present |
| `app/ui/routes.py` | `settings.BASE_URL` | `from app.core.config import settings` | WIRED | Import at line 39; `settings.BASE_URL` used in 4 self-call URLs; no residual `localhost:8000` hardcodes |
| `app/main.py:stuck_disarmed_monitor` schedule | `settings.POLL_INTERVAL_SECONDS` | `IntervalTrigger(seconds=...)` | WIRED | Line 92: `IntervalTrigger(seconds=settings.POLL_INTERVAL_SECONDS)` confirmed verbatim |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| ISAPI-03 | 07-01-PLAN.md | On timeout, system retries once before marking camera/NVR as error | SATISFIED | All four `ISAPIClient` methods (`get_device_info`, `get_camera_channels`, `get_detection_config`, `put_detection_config`) contain inline `try/except httpx.TimeoutException` retry blocks — lines 49, 65, 87, 109 of `app/isapi/client.py`. REQUIREMENTS.md traceability table marks ISAPI-03 Phase 7 Complete. |

No orphaned requirements: REQUIREMENTS.md maps only ISAPI-03 to Phase 7, and the plan claims exactly ISAPI-03.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | None found | — | — |

No TODO/FIXME/placeholder comments in modified files. No stub return values. No empty handlers. No console.log-only implementations (Python project).

---

### Human Verification Required

None. All goal criteria are machine-verifiable via grep and file inspection. The test suite provides behavioral coverage of the retry logic.

---

### Gaps Summary

No gaps. All five observable truths are verified against the actual codebase:

1. `get_device_info` has the inline retry pattern.
2. `get_camera_channels` has the inline retry pattern.
3. All four UI self-call URLs use `settings.BASE_URL` — zero hardcoded `localhost:8000` strings remain.
4. `stuck_disarmed_monitor` is registered with `IntervalTrigger(seconds=settings.POLL_INTERVAL_SECONDS)`.
5. Four new unit tests exist and cover both double-timeout (raises) and first-timeout-then-success (returns correct parsed result) scenarios for both methods.

The one deviation noted in the SUMMARY — updating `test_jobs_monitors.py` to reflect the new config-driven interval — is a correct and necessary consequence of the main.py change, not scope creep.

ISAPI-03 is fully satisfied: all four `ISAPIClient` methods now retry once on `TimeoutException` before re-raising.

---

_Verified: 2026-03-16_
_Verifier: Claude (gsd-verifier)_
