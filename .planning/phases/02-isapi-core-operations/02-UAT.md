---
status: complete
phase: 02-isapi-core-operations
source: [02-01-SUMMARY.md, 02-02-SUMMARY.md, 02-03-SUMMARY.md]
started: 2026-03-13T07:30:00Z
updated: 2026-03-15T00:00:00Z
---

## Current Test

[testing complete]

## Tests

### 1. ISAPI client detection config tests pass
expected: Run `python3 -m pytest tests/test_isapi_client.py -v` — all 10 tests pass covering GET/PUT for all 4 detection types, timeout retry once, non-timeout immediate raise, Digest auth and self-signed TLS settings.
result: skipped
reason: No real NVR available for integration testing; user proceeded to UI exploratory testing instead.

### 2. Disarm test suite passes
expected: Run `python3 -m pytest tests/test_disarm.py -v` — all 5 tests pass.
result: skipped
reason: Same as above.

### 3. Arm test suite passes
expected: Run `python3 -m pytest tests/test_arm.py -v` — all 4 tests pass.
result: skipped
reason: Same as above.

### 4. Full test suite — no regressions
expected: Run `python3 -m pytest tests/ -v` — all tests pass with 0 failures.
result: skipped
reason: Same as above.

### 5. POST /api/partitions/{id}/disarm — success response shape
expected: Disarm endpoint returns `{ success: true, data: { cameras_disarmed: N, cameras_kept_disarmed_by_other_partition: N, scheduled_rearm_at: null|datetime, errors: [] } }`.
result: skipped
reason: Deferred to real NVR testing.

### 6. POST /api/partitions/{id}/arm — success response shape
expected: Arm endpoint returns `{ success: true, data: { cameras_restored: N, cameras_kept_disarmed: N, errors: [] } }`.
result: skipped
reason: Deferred to real NVR testing.

### 7. Snapshot immutability — second disarm copies existing snapshot
expected: When camera is already disarmed (snapshot exists from partition A), disarming partition B does NOT call ISAPI GET again.
result: skipped
reason: Deferred to real NVR testing.

### 8. Refcount decrement — camera stays disarmed until all partitions arm
expected: Camera disarmed by two partitions: arming one decrements refcount but does NOT restore detection until both arm.
result: skipped
reason: Deferred to real NVR testing.

### 9. Location management UI — create/edit/delete locations
expected: A /locations page exists in the UI where operators can create new locations, edit and delete them. NVR Add form location dropdown is populated.
result: issue
reported: "nu am nici useri nu am nimic din ce am cerut..... am la adaugare nvr camp de locatie si e un dropdown gol"
severity: major
resolution: Fixed in session 2026-03-14 — /locations page created, nav link added, create/delete working.

## Summary

total: 9
passed: 0
issues: 1
pending: 0
skipped: 8

## Gaps

- truth: "Operators can create and manage locations through the UI before adding NVRs"
  status: resolved
  reason: "User reported: nu am nici useri nu am nimic din ce am cerut..... am la adaugare nvr camp de locatie si e un dropdown gol"
  severity: major
  test: 9
  root_cause: "Phase 05 did not include a /locations UI page — only the REST API was built in Phase 01"
  resolution: "Created /locations page with create/delete, added to nav, fixed NVR dropdown"
