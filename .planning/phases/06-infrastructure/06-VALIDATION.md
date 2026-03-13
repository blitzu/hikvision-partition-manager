---
phase: 6
slug: infrastructure
status: validated
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-11
audited: 2026-03-13
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio 0.23.x |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `pytest tests/test_infra.py -x -q` |
| **Full suite command** | `pytest tests/ -x -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_infra.py -x -q`
- **After every plan wave:** Run `pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 6-01-01 | 01 | 0 | INFRA-03, INFRA-05, INFRA-06 | unit | `python3 -m pytest tests/test_infra.py -x -q` | ✅ | ✅ green |
| 6-01-02 | 01 | 1 | INFRA-01 | manual smoke | `docker compose up -d && sleep 10 && curl -f http://localhost:8000/api/dashboard` | N/A | manual |
| 6-01-03 | 01 | 1 | INFRA-02 | manual build | `docker build -t hpm . && docker run --rm hpm whoami` | N/A | manual |
| 6-01-04 | 01 | 1 | INFRA-03 | unit | `python3 -m pytest tests/test_infra.py::test_env_example_has_all_vars -x` | ✅ | ✅ green |
| 6-02-01 | 02 | 2 | INFRA-05 | unit | `python3 -m pytest tests/test_infra.py::test_json_formatter -x` | ✅ | ✅ green |
| 6-02-02 | 02 | 2 | INFRA-05 | unit | `python3 -m pytest tests/test_infra.py::test_access_log_middleware -x` | ✅ | ✅ green |
| 6-02-03 | 02 | 2 | INFRA-06 | unit | `python3 -m pytest tests/test_infra.py::test_graceful_shutdown_drain -x` | ✅ | ✅ green |
| 6-02-04 | 02 | 2 | INFRA-07 | static audit | `grep -rn "text(f" app/ \|\| true` (0 matches — clean) | N/A | ✅ green |
| 6-02-05 | 02 | 2 | INFRA-04 | unit | `python3 -m pytest tests/test_infra.py::test_readme_has_required_sections -x` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `tests/test_infra.py` — 9 tests covering INFRA-03, INFRA-04, INFRA-05, INFRA-06
- [x] `app/core/logging.py` — JsonFormatter + setup_logging()
- [x] `app/middleware/__init__.py` — package init
- [x] `app/middleware/logging.py` — RequestLoggingMiddleware + request_id_var
- [x] `app/core/inflight.py` — in-flight ISAPI counter

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `docker compose up` starts with zero manual steps | INFRA-01 | Requires Docker daemon and network; not runnable in unit test | `docker compose up -d && sleep 10 && curl -f http://localhost:8000/api/dashboard && docker compose down` |
| Dockerfile builds with non-root user, multi-stage | INFRA-02 | Requires Docker build | `docker build -t hpm . && docker run --rm hpm whoami` — should output `appuser` |
| SIGTERM allows in-flight ISAPI calls to finish | INFRA-06 | Integration behavior; requires running containers | Start request, send SIGTERM mid-request, verify response still delivered and process exits cleanly |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 15s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-03-13

---

## Validation Audit 2026-03-13

| Metric | Count |
|--------|-------|
| Gaps found | 1 |
| Resolved | 1 |
| Escalated | 0 |
