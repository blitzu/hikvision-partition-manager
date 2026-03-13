---
phase: 05
slug: admin-ui
status: validated
nyquist_compliant: true
wave_0_complete: false
created: 2026-03-13
---

# Phase 05 — Validation Strategy

> Per-phase validation contract. Reconstructed from artifacts (State B) + gap-fill audit (2026-03-13).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 + pytest-asyncio 1.3.0 |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `python3 -m pytest tests/test_ui.py -x -q` |
| **Full suite command** | `python3 -m pytest tests/ -x -q` |
| **Estimated runtime** | ~2 seconds (UI tests only) |

---

## Sampling Rate

- **After every task commit:** Run `python3 -m pytest tests/test_ui.py -x -q`
- **After every plan wave:** Run `python3 -m pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~2 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 05-01-01 | 01 | 1 | UI-01: GET / returns 200 HTML with Dashboard heading | integration | `python3 -m pytest tests/test_ui.py::test_dashboard_returns_200_html -q` | ✅ | ✅ green |
| 05-01-02 | 01 | 1 | UI-01: Dashboard HTML contains HTMX every 10s polling | integration | `python3 -m pytest tests/test_ui.py::test_dashboard_contains_htmx_polling -q` | ✅ | ✅ green |
| 05-01-03 | 01 | 1 | UI-01: GET /partitions-partial returns 200 HTML | integration | `python3 -m pytest tests/test_ui.py::test_partitions_partial_returns_html -q` | ✅ | ✅ green |
| 05-01-04 | 01 | 1 | UI-01: POST /ui/partitions/{id}/disarm-row returns HTML tr | integration | `python3 -m pytest tests/test_ui.py::test_disarm_row_returns_html_tr -q` | ✅ | ✅ green |
| 05-01-05 | 01 | 1 | UI-01: POST /ui/partitions/{id}/arm-row returns HTML tr | integration | `python3 -m pytest tests/test_ui.py::test_arm_row_returns_html_tr -q` | ✅ | ✅ green |
| 05-01-06 | 01 | 1 | UI-02: GET /partitions/{id} returns 200 HTML with partition name | integration | `python3 -m pytest tests/test_ui.py::test_partition_detail_returns_200_html -q` | ✅ | ✅ green |
| 05-01-07 | 01 | 1 | UI-02: GET /partitions/{unknown-uuid} returns 404 HTML | integration | `python3 -m pytest tests/test_ui.py::test_partition_detail_404_for_unknown -q` | ✅ | ✅ green |
| 05-01-08 | 01 | 1 | UI-02: GET /ui/partitions/{id}/detail-partial returns 200 HTML | integration | `python3 -m pytest tests/test_ui.py::test_partition_detail_partial_returns_html -q` | ✅ | ✅ green |
| 05-01-09 | 01 | 1 | UI-02: POST /ui/partitions/{id}/disarm-detail returns 200 HTML body | integration | `python3 -m pytest tests/test_ui.py::test_disarm_detail_returns_html_body -q` | ✅ | ✅ green |
| 05-01-10 | 01 | 1 | UI-02: POST /ui/partitions/{id}/arm-detail returns 200 HTML body | integration | `python3 -m pytest tests/test_ui.py::test_arm_detail_returns_html_body -q` | ✅ | ✅ green |
| 05-02-01 | 02 | 2 | UI-03: GET /partitions/new returns 200 HTML with form fields | integration | `python3 -m pytest tests/test_ui.py::test_partition_new_form_returns_html_with_form_fields -q` | ✅ | ✅ green |
| 05-02-02 | 02 | 2 | UI-03: GET /partitions/{id}/edit returns 200 HTML with pre-filled name | integration | `python3 -m pytest tests/test_ui.py::test_partition_edit_form_returns_html_prefilled -q` | ✅ | ✅ green |
| 05-02-03 | 02 | 2 | UI-03: POST /ui/partitions/create redirects 303 to /partitions/{id} | integration | `python3 -m pytest tests/test_ui.py::test_partition_create_redirects_on_success -q` | ✅ | ✅ green |
| 05-02-04 | 02 | 2 | UI-04: GET /nvrs returns 200 HTML with NVR content | integration | `python3 -m pytest tests/test_ui.py::test_nvrs_page_returns_200_html -q` | ✅ | ✅ green |
| 05-02-05 | 02 | 2 | UI-04: GET /ui/nvrs/{id}/detail returns 200 HTML camera partial | integration | `python3 -m pytest tests/test_ui.py::test_nvr_detail_partial_returns_html -q` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| HTMX polling updates DOM every 10s without page reload | UI-01, UI-02 | Requires live browser with HTMX runtime | Open dashboard in browser, observe table updates every 10s |
| ARM/DISARM confirmation modal opens/closes | UI-01, UI-02 | Requires browser JS dialog API | Click ARM/DISARM button, verify dialog opens; confirm, verify row updates |
| Per-NVR Sync replaces only that NVR section | UI-03 | Requires browser JS + hx-vals expression | Open /partitions/new, click Sync on one NVR section, verify only that section updates |
| NVR Test Connectivity shows inline result | UI-04 | Route proxies to localhost:8000 (not available in test env) | Open /nvrs in browser, click Test button, verify inline span updates with Online/Offline |
| State badge colors (green/yellow/orange/red dots) | UI-01-04 | CSS rendering | Inspect rendered state badges visually in browser |
| Overdue row tint visible for overdue partitions | UI-01 | CSS rendering | Set up overdue partition, verify row has yellow-pale tint |
| Auto-rearm countdown shows minutes remaining | UI-02 | Requires live data with scheduled_rearm_at | Disarm partition with auto_rearm_minutes set, check detail page countdown |

---

## Bug Fixed During Validation

**Route ordering bug in app/ui/routes.py** — `GET /partitions/new` was registered after `GET /partitions/{partition_id}`, causing FastAPI to capture `/partitions/new` as `partition_id="new"` and return 422 (UUID validation failure). Fixed by moving the `/partitions/new` handler before the `{partition_id}` handler in the file.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 2s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-03-13

---

## Validation Audit 2026-03-13

| Metric | Count |
|--------|-------|
| Gaps found | 15 |
| Resolved | 15 |
| Escalated (impl bug — fixed) | 1 |
