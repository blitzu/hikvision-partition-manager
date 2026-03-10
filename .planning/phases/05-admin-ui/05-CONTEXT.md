# Phase 5: Admin UI - Context

**Gathered:** 2026-03-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Four web pages for operators: Dashboard (partition overview, ARM/DISARM quick actions),
Partition Detail (per-camera status, audit log, arm/disarm with impact modal), Partition
Editor (create/edit with camera selector), NVR Management (add NVR, test connectivity,
view cameras). Stack is locked: HTMX + Jinja2 + Pico CSS. No authentication (out of scope).

</domain>

<decisions>
## Implementation Decisions

### State Badges & Visual Language
- **Badge style**: Colored dot + text label. Colors: green = armed, yellow = disarmed,
  orange = partial, red = error. Works natively with Pico CSS custom properties.
- **PARTIAL detail**: Text secondary below the badge — `"PARTIAL • 3/5 cameras"` — always
  visible without hover. More accessible than tooltip-only.
- **Overdue highlight**: Full row background tinted yellow-pale + ⚠ icon next to the
  disarmed duration. Visually impossible to miss without being aggressive.
- **Duration column**: Dedicated "Duration" column in dashboard table. Shows elapsed time
  for disarmed/partial/error partitions, empty for armed. Updates every 10s auto-refresh.

### Confirmation Modals
- **DISARM modal**: Shows full impact — number of cameras affected, calculated auto-rearm
  time (if `auto_rearm_minutes` is set), and an optional free-text "Reason" field
  (`disarmed_by` is pre-filled from session context, reason is optional).
- **ARM modal**: Simple confirmation only — "Arm [Partition Name]?" + Yes/Cancel.
  Refcount details visible on detail page; no need to repeat in the modal.
- **After confirm**: Modal closes, HTMX re-fetches the partition row/section without full
  page reload. Updated state appears immediately.

### Camera Selector (Partition Editor)
- **Control type**: Checkboxes grouped by NVR header. Each NVR section has a "Sync" button.
  Works well with Pico CSS, no extra JS library needed.
- **Per-NVR sync**: HTMX partial refresh — only that NVR's section re-fetches from the
  server. Newly discovered cameras appear unchecked. Existing selections preserved.
- **NVR with no cameras**: NVR appears in selector with message "No cameras synced yet —
  sync first" + Sync button visible. Operator can trigger sync inline without leaving editor.
- **Editor pages**: Separate full pages — `/partitions/new` (create) and
  `/partitions/{id}/edit` (edit). Not inline on detail page. Clear URLs, simpler Jinja2.

### Navigation & Page Structure
- **Top navbar**: Simple header with title "Partition Manager" + two nav links:
  Dashboard | NVRs. Pico CSS `<nav>` component. No side nav needed for 4 pages.
- **Dashboard → Detail navigation**: Explicit "View" button per row (not name click).
  More discoverable for operators unfamiliar with the UI.
- **Detail page header**: "Edit" button in top-right corner → navigates to
  `/partitions/{id}/edit`. Detail page is otherwise read-only.
- **NVR Management page**: Expandable per-NVR sections showing synced cameras (HTMX
  toggle). Also includes: add NVR form + inline connectivity test button.

### Claude's Discretion
- Exact Pico CSS color variable names for state dot colors
- HTML structure of the HTMX polling container on dashboard and detail page
- Template inheritance hierarchy (base.html, partials)
- Auto-rearm countdown implementation (server-rendered remaining time, refreshed by 10s poll)
- Pagination controls for audit log (simple prev/next vs numbered pages)

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `GET /api/dashboard` — returns all partitions with state, `disarmed_minutes`, `overdue` flag,
  active-first sort. Dashboard page consumes this directly.
- `GET /api/partitions/{id}/state` — returns per-camera detection status + refcounts. Detail page.
- `GET /api/partitions/{id}/audit` — paginated audit log. Detail page last-20 section.
- `POST /api/partitions/{id}/arm` and `.../disarm` — called by modals after confirmation.
- `GET /api/nvrs/{id}/test` — used by NVR management inline test button.
- `GET /api/nvrs/{id}/cameras/sync` — used by per-NVR sync button in camera selector.

### Established Patterns
- All API responses use `APIResponse[T]` envelope: `{ success, data, error }`.
- Partition states: `armed`, `disarmed`, `partial`, `error` (enum defined in models).
- `overdue` flag already computed by dashboard service — no client-side calculation needed.
- `disarmed_minutes` already computed server-side — display directly in Duration column.

### Integration Points
- New `app/templates/` directory — Jinja2 templates served by FastAPI with `Jinja2Templates`.
- New `app/static/` directory — CSS overrides, any minimal JS for modal behavior.
- `app/main.py` — add Jinja2 template routes (separate from API routes, no `/api` prefix).
- Existing API routes stay untouched — UI pages call them via HTMX or standard form POSTs.

</code_context>

<specifics>
## Specific Ideas

- Pico CSS classless approach preferred — minimal custom CSS, rely on semantic HTML.
- Dashboard table rows are the primary interaction surface — each row has state badge,
  duration, overdue indicator, View button, ARM/DISARM quick buttons.
- Auto-refresh via HTMX `hx-trigger="every 10s"` on the partition list container.
- NVR expandable sections on /nvrs page use HTMX `hx-get` + `hx-swap="innerHTML"`.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 05-admin-ui*
*Context gathered: 2026-03-10*
