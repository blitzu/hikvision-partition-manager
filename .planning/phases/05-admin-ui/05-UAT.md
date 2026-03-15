---
status: complete
phase: 05-admin-ui
source: [05-01-SUMMARY.md, 05-02-SUMMARY.md]
started: 2026-03-14T20:00:00Z
updated: 2026-03-15T00:00:00Z
---

## Current Test

[testing complete]

## Tests

### 1. App boots from cold start
expected: docker compose up --build starts without errors. Migrations run. Server responds on :8000.
result: issue
reported: "ModuleNotFoundError: No module named 'sniffio'"
severity: blocker
resolution: Added `sniffio>=1.3` to pyproject.toml dependencies.

### 2. Location management UI exists
expected: /locations page lets operators create and delete locations. Nav has Locations link. NVR Add form has populated location dropdown.
result: issue
reported: "nu am nici useri nu am nimic din ce am cerut..... am la adaugare nvr camp de locatie si e un dropdown gol"
severity: major
resolution: Created /locations page (create/delete), added Locations to nav bar, NVR dropdown now works.

### 3. New Partition button visible on dashboard
expected: Dashboard has a visible link/button to create a new partition.
result: issue
reported: "nu vad unde definesc partitiile"
severity: major
resolution: Added "+ New Partition" button (float right) in dashboard heading.

### 4. Audit log populated after arm/disarm
expected: Recent Activity section on partition detail shows entries after each arm/disarm.
result: issue
reported: "e un bug" (audit log empty despite multiple arm/disarm operations)
severity: major
root_cause: "disarm_partition and arm_partition early-exit path (no cameras) committed state change without writing PartitionAuditLog entry"
resolution: Added PartitionAuditLog write in the no-cameras early-exit path for both disarm and arm.

### 5. Auto-rearm fires after configured delay
expected: Partition with auto_rearm_minutes set automatically transitions back to armed after that many minutes.
result: issue
reported: "vad ca nu se autoarmeaza dupa timpul setat"
severity: major
root_cause: "Same no-cameras early-exit path did not set state.scheduled_rearm_at or call schedule_rearm()"
resolution: Added scheduled_rearm_at calculation and schedule_rearm() call in the no-cameras path.

### 6. Audit log shows seconds and operator reason
expected: Audit log timestamps include HH:MM:SS. Reason typed by operator at disarm is shown in Reason column.
result: issue
reported: "ar trebui sa am si secunda la care se intampla si la disarm sa apara si textul scris de operator"
severity: minor
resolution: Added Reason column to audit table. Changed timestamp format to %Y-%m-%d %H:%M:%S.

### 7. Timestamps shown in local timezone
expected: All dates/times in UI show Europe/Bucharest time, not UTC.
result: issue
reported: "timpul afisat la audit e fara timezoneul meu"
severity: minor
resolution: Added localdt Jinja2 filter (ZoneInfo Europe/Bucharest) applied to all timestamps in templates.

### 8. NVR list shows location column and delete button
expected: NVR management page shows which location each NVR belongs to, and has a Delete button per row.
result: issue
reported: "buton de sters nvr-uri nu am?" + "nvr ar trebui sa fie atribuit unei locatii"
severity: major
resolution: Added Location column (via locations_by_id dict passed from route) and Delete button with cascade delete of cameras.

### 9. Partition delete button exists
expected: Partition detail page has a Delete button. Blocked if partition is disarmed.
result: issue
reported: "nici partitiile nu pot sa le sterg"
severity: major
resolution: Added Delete button on partition_detail.html, wired to new /ui/partitions/{id}/delete route using existing delete_partition() service.

### 10. Delete NVR and Location without server error
expected: Clicking Delete on NVR or Location succeeds. No Internal Server Error.
result: issue
reported: "cand sterg nvr primesc Internal Server Error la fel si la locatie"
severity: blocker
root_cause: "SQLAlchemy ORM db.delete() fails on FK-constrained rows. Cameras, snapshots, refcounts, and partition_cameras must be deleted first."
resolution: Replaced ORM delete with explicit sql_delete() in correct FK order for both NVR and Location delete routes.

## Summary

total: 10
passed: 0
issues: 10
pending: 0
skipped: 0

## Gaps

- truth: "App starts from cold start without errors"
  status: resolved
  reason: "ModuleNotFoundError: No module named 'sniffio'"
  severity: blocker
  test: 1
  root_cause: "sniffio is a direct dependency of apscheduler SQLAlchemy data store but was not declared in pyproject.toml"
  resolution: "Added sniffio>=1.3 to pyproject.toml"

- truth: "Location management UI exists and NVR dropdown is populated"
  status: resolved
  reason: "User reported: dropdown gol"
  severity: major
  test: 2
  root_cause: "Phase 05 only built partition/NVR UI — no /locations page was planned or built"
  resolution: "Created app/templates/locations.html, added GET /locations + POST /ui/locations/create + POST /ui/locations/{id}/delete routes"

- truth: "Dashboard has visible New Partition button"
  status: resolved
  reason: "User reported: nu vad unde definesc partitiile"
  severity: major
  test: 3
  root_cause: "Route existed (/partitions/new) but no link from anywhere in the UI"
  resolution: "Added + New Partition button in dashboard.html heading"

- truth: "Audit log is written on every arm/disarm including partitions with no cameras"
  status: resolved
  reason: "Audit log empty despite multiple operations"
  severity: major
  test: 4
  root_cause: "Early-exit branch in disarm_partition and arm_partition (when cameras list is empty) returned before writing PartitionAuditLog"
  artifacts:
    - path: "app/partitions/service.py"
      issue: "no-cameras early-exit missing audit write"
  resolution: "Added PartitionAuditLog insert before commit in both no-cameras paths"

- truth: "Auto-rearm schedules correctly after disarm"
  status: resolved
  reason: "Partition did not rearm after configured delay"
  severity: major
  test: 5
  root_cause: "No-cameras early-exit in disarm_partition did not set state.scheduled_rearm_at or call schedule_rearm()"
  artifacts:
    - path: "app/partitions/service.py"
      issue: "no-cameras path missing schedule_rearm call"
  resolution: "Added scheduled_rearm_at calculation and schedule_rearm() call in no-cameras path"

- truth: "NVR and Location delete work without errors"
  status: resolved
  reason: "Internal Server Error on delete"
  severity: blocker
  test: 10
  root_cause: "FK constraint violations: cameras/snapshots/refcounts reference NVRs; NVRs reference locations. ORM delete does not cascade."
  resolution: "Explicit sql_delete() in FK order: snapshots → refcounts → partition_cameras → cameras → nvr_devices → locations"
