---
phase: 05-admin-ui
plan: "02"
subsystem: admin-ui
tags: [htmx, jinja2, partitions, nvrs, forms, pico-css]
dependency_graph:
  requires: [05-01]
  provides: [partition-create-edit-ui, nvr-management-ui]
  affects: [app/ui/routes.py, app/templates/]
tech_stack:
  added: []
  patterns:
    - HTMX per-section swap with hx-vals JS expression for selected camera state
    - httpx internal proxy for NVR test and sync routes
    - Jinja2 include with with-block variable scoping for partials
key_files:
  created:
    - app/templates/partition_form.html
    - app/templates/partials/nvr_camera_section.html
    - app/templates/nvrs.html
    - app/templates/partials/nvr_detail_section.html
  modified:
    - app/ui/routes.py
decisions:
  - hx-vals JS expression used for Sync button to collect currently-checked camera_ids without a form submission
  - httpx internal calls are best-effort (try/except) in sync partial — DB query runs regardless of ISAPI result
  - POST /ui/nvrs/create proxies to /api/locations/{id}/nvrs to keep password encryption in one place
  - partitions/{id}/edit route placed before partitions/{id} generic catch-all would conflict — FastAPI handles path ordering correctly since /edit is a literal suffix
metrics:
  duration: "~8 min"
  completed_date: "2026-03-11"
  tasks: 2
  files: 5
---

# Phase 5 Plan 2: Partition Form and NVR Management Pages Summary

Partition create/edit form with grouped camera selector and per-NVR HTMX sync, plus NVR management page with inline connectivity test and expandable camera detail panel.

## What Was Built

**Task 1 — Partition create/edit form**

Added `_get_nvrs_with_cameras(db)` helper that loads all NVRDevice rows then their Camera rows from DB (no ISAPI). Added six routes to `app/ui/routes.py`:

- `GET /partitions/new` — renders empty `partition_form.html`
- `GET /partitions/{id}/edit` — renders pre-filled form with `selected_camera_ids` set from existing cameras
- `POST /ui/partitions/create` — calls `create_partition()`, redirects to new partition detail on success
- `POST /ui/partitions/{id}/update` — calls `update_partition()` + `sync_partition_cameras()`, redirects
- `GET /ui/nvrs/{id}/cameras` — returns `nvr_camera_section.html` partial from DB (no ISAPI)
- `GET /ui/nvrs/{id}/cameras/sync` — fires best-effort httpx sync then returns partial from DB

`partition_form.html` extends `base.html`, has all four fields (name, description, auto_rearm_minutes, alert_if_disarmed_minutes), loops over NVR sections via Jinja2 `{% include %}` with `{% with %}` block.

`partials/nvr_camera_section.html` wraps each NVR section in `<div id="nvr-section-{nvr.id}">` so HTMX can swap it. The Sync button uses `hx-vals='js:{...}'` to collect checked camera_ids before the request fires.

**Task 2 — NVR management page**

Added four routes:

- `GET /nvrs` — queries all NVRDevice and Location rows, renders `nvrs.html`
- `GET /ui/nvrs/{id}/detail` — returns `nvr_detail_section.html` partial with camera list
- `GET /ui/nvrs/{id}/test` — proxies to `/api/nvrs/{id}/test` via httpx, returns inline HTML `<span>` with green/red result
- `POST /ui/nvrs/create` — proxies to `/api/locations/{location_id}/nvrs` via httpx, redirects to `/nvrs` on success

`nvrs.html` extends `base.html`. Has a `<details>` collapsed Add NVR form with location dropdown. NVR table includes status dot (reusing `state-armed`/`state-error` CSS classes), last-seen timestamp, Test button (hx-get targeting result span), and Show Cameras button (hx-get targeting colspan row).

`partials/nvr_detail_section.html` renders camera table or empty-state message.

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check

Files created:
- app/templates/partition_form.html — present
- app/templates/partials/nvr_camera_section.html — present
- app/templates/nvrs.html — present
- app/templates/partials/nvr_detail_section.html — present
- app/ui/routes.py — modified with all new routes

Routes verified: all 4 required routes (/partitions/new, /nvrs, /ui/nvrs/{nvr_id}/test, /ui/nvrs/{nvr_id}/detail) present.

## Self-Check: PASSED
