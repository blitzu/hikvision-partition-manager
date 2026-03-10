---
phase: 1
slug: foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-10
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-asyncio |
| **Config file** | `pyproject.toml` — `[tool.pytest.ini_options]` (Wave 0 installs) |
| **Quick run command** | `pytest tests/ -x -q` |
| **Full suite command** | `pytest tests/ -v --tb=short` |
| **Estimated runtime** | ~30 seconds (integration tests require PostgreSQL) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x -q`
- **After every plan wave:** Run `pytest tests/ -v --tb=short`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 1-01-01 | 01 | 0 | DATA-01..09 | integration | `pytest tests/test_schema.py -x -q` | ❌ W0 | ⬜ pending |
| 1-01-02 | 01 | 1 | DATA-01..09 | integration | `pytest tests/test_schema.py -x -q` | ❌ W0 | ⬜ pending |
| 1-02-01 | 02 | 1 | NVR-01 | integration | `pytest tests/test_locations.py -x -q` | ❌ W0 | ⬜ pending |
| 1-02-02 | 02 | 1 | NVR-02, NVR-06 | integration | `pytest tests/test_nvrs.py::test_password_encrypted tests/test_nvrs.py::test_password_not_in_response -x -q` | ❌ W0 | ⬜ pending |
| 1-02-03 | 02 | 1 | NVR-03, NVR-05 | unit | `pytest tests/test_nvrs.py::test_connectivity tests/test_nvrs.py::test_last_seen_updated -x -q` | ❌ W0 | ⬜ pending |
| 1-03-01 | 03 | 2 | NVR-04 | integration | `pytest tests/test_cameras.py::test_sync_upsert -x -q` | ❌ W0 | ⬜ pending |
| 1-03-02 | 03 | 2 | NVR-03, NVR-05 | unit | `pytest tests/test_nvrs.py::test_connectivity -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

All test infrastructure is new (greenfield project):

- [ ] `tests/conftest.py` — engine (session-scoped), db_session (function-scoped with rollback), client (AsyncClient with dependency override)
- [ ] `tests/mocks.py` — MockISAPIClient with get_device_info and get_camera_channels
- [ ] `tests/test_schema.py` — DATA-01 through DATA-09 table existence tests (9 tables, correct columns)
- [ ] `tests/test_locations.py` — NVR-01 location CRUD + timezone validation
- [ ] `tests/test_nvrs.py` — NVR-02 (encryption), NVR-03 (connectivity), NVR-05 (last_seen_at), NVR-06 (password not in response)
- [ ] `tests/test_cameras.py` — NVR-04 sync + upsert dedup (re-sync doesn't duplicate)
- [ ] Framework install: `pytest>=8.0 pytest-asyncio>=0.23 httpx>=0.27` added to `pyproject.toml` dev dependencies
- [ ] Test PostgreSQL: `TEST_DATABASE_URL` in `.env.test` pointing to a test DB (or `docker compose up -d postgres`)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Camera sync with real NVR device | NVR-04, NVR-03 | Requires physical NVR on network; ISAPI endpoint path may vary by firmware | Run `GET /api/nvrs/{id}/cameras/sync` against real NVR; verify channels appear in DB; verify no duplicates on re-sync |
| NVR password never appears in logs | NVR-06 | Log output inspection | Enable LOG_LEVEL=DEBUG, run NVR create + test connectivity, grep logs for plaintext password string |
| Alembic migration from fresh DB | DATA-01..09 | Requires real PostgreSQL with empty DB | `docker compose down -v && docker compose up -d && alembic upgrade head`; inspect schema |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
