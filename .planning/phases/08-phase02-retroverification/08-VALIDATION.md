---
phase: 8
slug: phase02-retroverification
status: draft
nyquist_compliant: false
wave_0_complete: true
created: 2026-03-17
---

# Phase 8 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 + pytest-asyncio 1.3.0 |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `python3 -m pytest tests/test_isapi_client.py tests/test_disarm.py tests/test_arm.py -v` |
| **Full suite command** | `python3 -m pytest tests/ -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python3 -m pytest tests/test_isapi_client.py tests/test_disarm.py tests/test_arm.py -v`
- **After every plan wave:** Run `python3 -m pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 8-01-01 | 01 | 1 | ISAPI-01..05 | code inspection | `python3 -m pytest tests/test_isapi_client.py -v` | ✅ | ⬜ pending |
| 8-01-02 | 01 | 1 | DARM-01..09 | integration | `python3 -m pytest tests/test_disarm.py -v` | ✅ | ⬜ pending |
| 8-01-03 | 01 | 1 | DARM-10 | inspection | code review of asyncio.gather() at service.py:256 | ✅ | ⬜ pending |
| 8-01-04 | 01 | 1 | ARM-01..07 | integration | `python3 -m pytest tests/test_arm.py -v` | ✅ | ⬜ pending |
| 8-01-05 | 01 | 1 | All 22 | file check | `test -f .planning/phases/02-isapi-core-operations/02-VERIFICATION.md` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

*Existing infrastructure covers all phase requirements. This is a documentation-only phase (no new code expected unless a gap is found during audit).*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| DARM-10: ISAPI calls to cameras on same NVR are parallel | DARM-10 | Parallelism is structural; no automated timing test exists | Read `app/partitions/service.py` — confirm `asyncio.gather()` at line ~256 and `asyncio.Lock()` at line ~172 |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
