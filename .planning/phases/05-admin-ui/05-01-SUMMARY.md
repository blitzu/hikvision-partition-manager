---
phase: 05-admin-ui
plan: 01
subsystem: ui
tags: [htmx, jinja2, pico-css, templates, html, fastapi]

# Dependency graph
requires:
  - phase: 03-partition-api
    provides: "get_dashboard, get_partition_state, get_partition_audit_log, disarm_partition, arm_partition service functions"
  - phase: 04-automation-alerts
    provides: "auto-rearm scheduling (scheduled_rearm_at on PartitionState)"

provides:
  - "HTMX-powered admin UI at / (dashboard) and /partitions/{id} (detail page)"
  - "app/ui/routes.py with ui_router: 8 routes (GET dashboard, GET detail, GET partials, POST arm/disarm x4)"
  - "app/templates/ with base.html, dashboard.html, partition_detail.html, 404.html"
  - "app/templates/partials/ with partition_rows.html, partition_row_single.html, partition_detail_body.html"
  - "app/static/style.css with state badge dots and overdue row tint"

affects: [05-02-nvr-management, 05-03-partition-editor]

# Tech tracking
tech-stack:
  added: [jinja2>=3.1, python-multipart>=0.0.9, pico-css@2 (CDN), htmx@2.0.4 (CDN)]
  patterns:
    - "UI thin-endpoint pattern: POST /ui/partitions/{id}/disarm-row and disarm-detail serve different partials for dashboard vs detail context"
    - "HTMX polling: hx-trigger='every 10s' on container; innerHTML swap keeps modals working"
    - "Jinja2Templates directory='app/templates'; partials referenced as 'partials/filename.html'"

key-files:
  created:
    - app/ui/__init__.py
    - app/ui/routes.py
    - app/templates/base.html
    - app/templates/dashboard.html
    - app/templates/partition_detail.html
    - app/templates/404.html
    - app/templates/partials/partition_rows.html
    - app/templates/partials/partition_row_single.html
    - app/templates/partials/partition_detail_body.html
    - app/static/style.css
  modified:
    - app/main.py
    - pyproject.toml

key-decisions:
  - "Two separate POST endpoint suffixes (-row vs -detail) to return the correct partial for dashboard vs detail page context after arm/disarm"
  - "StaticFiles mounted before ui_router include in app/main.py to ensure /static resolves before wildcard UI routes"
  - "jinja2 and python-multipart added to pyproject.toml dependencies (were missing from project spec)"
  - "Modals use native HTML <dialog> element styled by Pico CSS — no custom JS modal library needed"
  - "rearm_in_minutes computed server-side in route handler and passed to template — avoids JS datetime math in templates"

patterns-established:
  - "HTMX polling partial: container div has hx-get, hx-trigger='every 10s', hx-swap='innerHTML'; initial render uses {% include %}"
  - "ARM/DISARM confirmation dialogs: showModal() on button click; hx-on::after-request closes dialog after HTMX swap completes"
  - "Dashboard row HTMX swap: hx-target='#row-{id}', hx-swap='outerHTML' replaces the entire <tr>"
  - "Detail body HTMX swap: hx-target='#detail-body', hx-swap='innerHTML' replaces section content"

requirements-completed: [UI-01, UI-02]

# Metrics
duration: 18min
completed: 2026-03-11
---

# Phase 5 Plan 01: Admin UI Dashboard and Partition Detail Summary

**HTMX + Jinja2 admin UI with live-polling dashboard, per-row arm/disarm modals, and partition detail with camera status and audit log**

## Performance

- **Duration:** 18 min
- **Started:** 2026-03-11T05:53:01Z
- **Completed:** 2026-03-11T06:11:00Z
- **Tasks:** 3
- **Files modified:** 12

## Accomplishments

- Full template infrastructure: base.html (Pico CSS + HTMX CDN), static CSS with state badges and overdue tints
- Dashboard at `/` with HTMX 10s polling, state badge dots, overdue row highlight, ARM/DISARM confirmation dialogs using native `<dialog>`
- Partition detail at `/partitions/{id}` with camera status table, paginated audit log, auto-rearm countdown, and inline ARM/DISARM modals

## Task Commits

Each task was committed atomically:

1. **Task 1: Template infrastructure — base.html, static setup, and UI router skeleton** - `3947fcf` (feat)
2. **Task 2: Dashboard page — HTMX polling table with state badges, overdue highlight, and ARM/DISARM modals** - `7210cce` (feat)
3. **Task 3: Partition detail page — camera status, audit log, arm/disarm modal, auto-rearm countdown** - `55e4c09` (feat)

## Files Created/Modified

- `app/ui/__init__.py` — Empty package marker for UI module
- `app/ui/routes.py` — ui_router with 8 routes: GET /, GET /partitions/{id}, GET /partitions-partial, GET /ui/partitions/{id}/detail-partial, POST disarm-row, POST arm-row, POST disarm-detail, POST arm-detail
- `app/templates/base.html` — HTML5 base with Pico CSS classless CDN, HTMX 2.x CDN, nav bar with Dashboard/NVRs links
- `app/templates/dashboard.html` — Dashboard page extending base, HTMX-polled tbody, ARM/DISARM dialogs per row
- `app/templates/partition_detail.html` — Partition detail extending base, static metadata, ARM/DISARM modals, HTMX-polled #detail-body
- `app/templates/404.html` — Simple 404 page for missing partitions
- `app/templates/partials/partition_rows.html` — tbody row loop for dashboard HTMX polling
- `app/templates/partials/partition_row_single.html` — Single row for HTMX outerHTML swap after dashboard arm/disarm
- `app/templates/partials/partition_detail_body.html` — Detail body with state, camera table, audit log, pagination
- `app/static/style.css` — State badge dot colors, overdue row tint, dialog sizing
- `app/main.py` — Added StaticFiles mount and ui_router include
- `pyproject.toml` — Added jinja2 and python-multipart dependencies

## Decisions Made

- Used two POST endpoint suffixes (`-row` vs `-detail`) so dashboard and detail page each get the correct partial HTML after an arm/disarm action without the route needing to guess context from headers.
- `rearm_in_minutes` computed server-side in Python (`max(0, int(delta // 60))`) and passed to template — avoids pushing datetime math into Jinja2.
- `<dialog>` element used for modals — Pico CSS styles it natively with no custom JS overlay needed.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Installed missing jinja2 and python-multipart dependencies**
- **Found during:** Task 1 verification
- **Issue:** jinja2 not installed (AssertionError in Jinja2Templates init); python-multipart not installed (RuntimeError on Form() route registration)
- **Fix:** Installed both packages via pip; added to pyproject.toml dependencies
- **Files modified:** pyproject.toml
- **Verification:** `python3 -c "from app.ui.routes import ui_router"` succeeds
- **Committed in:** 3947fcf (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 3 - Blocking)
**Impact on plan:** Necessary missing dependencies for template rendering and form handling. No scope creep.

## Issues Encountered

None beyond the missing dependency install handled via deviation Rule 3.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Dashboard and partition detail pages are fully operational (render with real data from existing service layer)
- Ready for Phase 5 Plan 02: NVR management UI pages
- Ready for Phase 5 Plan 03: Partition editor UI (create/edit forms)

---
*Phase: 05-admin-ui*
*Completed: 2026-03-11*
