---
phase: 7
slug: isapi-retry-fix
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-15
---

# Phase 7 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio 0.23 |
| **Config file** | `pyproject.toml` — `[tool.pytest.ini_options]` asyncio_mode = "auto" |
| **Quick run command** | `pytest tests/test_isapi_client.py -x` |
| **Full suite command** | `pytest tests/ -x` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_isapi_client.py -x`
- **After every plan wave:** Run `pytest tests/ -x`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 7-01-01 | 01 | 1 | ISAPI-03 | unit | `pytest tests/test_isapi_client.py -x -k "device_info"` | ❌ Wave 0 | ⬜ pending |
| 7-01-02 | 01 | 1 | ISAPI-03 | unit | `pytest tests/test_isapi_client.py -x -k "camera_channels"` | ❌ Wave 0 | ⬜ pending |
| 7-01-03 | 01 | 1 | BASE_URL | smoke | `grep -r "localhost:8000" app/ui/routes.py` (zero hits) | manual | ⬜ pending |
| 7-01-04 | 01 | 1 | POLL | smoke | `pytest tests/ -x` | manual | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_isapi_client.py` — add 4 new test functions for `get_device_info` and `get_camera_channels` retry behavior (double-timeout raises, first-timeout-then-success for each)

*Existing test infrastructure (conftest.py, fixtures, framework) covers all other phase requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `settings.BASE_URL` used in all 4 UI routes | BASE_URL | Mechanical substitution; grep verification sufficient | `grep -r "localhost:8000" app/ui/routes.py` must return zero hits |
| `POLL_INTERVAL_SECONDS` wired to scheduler | POLL | Timing not unit-tested; code review sufficient | `grep "POLL_INTERVAL_SECONDS" app/main.py` must show `IntervalTrigger(seconds=settings.POLL_INTERVAL_SECONDS)` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
