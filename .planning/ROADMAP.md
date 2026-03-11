# Roadmap: Virtual Partition Management System

## Overview

Six phases take the service from an empty repo to a fully deployed microservice. Phase 1 builds the foundation — schema and NVR/camera CRUD. Phase 2 implements the ISAPI HTTP client and the disarm/arm core logic that is the product's reason for existing. Phase 3 exposes a complete REST API including partition management. Phase 4 adds automation via scheduled jobs and webhook alerts. Phase 5 delivers the HTMX admin UI on top of the API. Phase 6 wraps the service in Docker, structured logging, and a README so it can be shipped and operated with zero manual steps.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Foundation** - Database schema, migrations, location/NVR/camera CRUD and encryption (completed 2026-03-10)
- [x] **Phase 2: ISAPI Core Operations** - HTTP Digest client, disarm and arm operations with refcount logic (completed 2026-03-10)
- [x] **Phase 3: Partition API** - Partition CRUD, REST API surface, audit log and state endpoints (completed 2026-03-10)
- [x] **Phase 4: Automation & Alerts** - Background jobs (auto-rearm, stuck monitor, NVR health) and webhook delivery (completed 2026-03-11)
- [x] **Phase 5: Admin UI** - HTMX + Jinja2 dashboard, partition detail, editor, and NVR management pages (completed 2026-03-11)
- [ ] **Phase 6: Infrastructure** - Docker Compose deployment, structured logging, graceful shutdown, README

## Phase Details

### Phase 1: Foundation
**Goal**: The data layer exists and operators can manage locations, NVRs, and cameras through a working API
**Depends on**: Nothing (first phase)
**Requirements**: DATA-01, DATA-02, DATA-03, DATA-04, DATA-05, DATA-06, DATA-07, DATA-08, DATA-09, NVR-01, NVR-02, NVR-03, NVR-04, NVR-05, NVR-06
**Success Criteria** (what must be TRUE):
  1. A POST to create a location, then an NVR, then sync cameras succeeds end-to-end with a real NVR device
  2. NVR passwords are stored encrypted at rest and never appear in any API response or log line
  3. Syncing cameras from the NVR upserts existing cameras by (nvr_id, channel_no) without creating duplicates
  4. Connectivity test endpoint returns deviceInfo on success and a clear error when the NVR is unreachable
  5. All nine schema tables exist with correct constraints and relationships, verified by migration running clean from empty database
**Plans**: 3 plans

Plans:
- [x] 01-01-PLAN.md — Project scaffold, all 9 ORM models, Alembic migration, test infrastructure
- [x] 01-02-PLAN.md — Location and NVR CRUD with Fernet password encryption
- [x] 01-03-PLAN.md — ISAPIClient, camera sync with upsert, NVR connectivity test

### Phase 2: ISAPI Core Operations
**Goal**: Disarming a partition disables detection on all member cameras via ISAPI, and arming restores exact saved state while respecting multi-partition refcount
**Depends on**: Phase 1
**Requirements**: ISAPI-01, ISAPI-02, ISAPI-03, ISAPI-04, ISAPI-05, DARM-01, DARM-02, DARM-03, DARM-04, DARM-05, DARM-06, DARM-07, DARM-08, DARM-09, DARM-10, ARM-01, ARM-02, ARM-03, ARM-04, ARM-05, ARM-06, ARM-07
**Success Criteria** (what must be TRUE):
  1. POSTing disarm disables all enabled detection types on every camera in the partition via ISAPI within a single operation
  2. POSTing arm on a camera that belongs to one disarmed partition restores its detection config from the saved snapshot exactly
  3. POSTing arm on a camera that belongs to two disarmed partitions does NOT restore detection until both partitions are armed
  4. A camera that is already disarmed (snapshot exists) retains its original snapshot when a second disarm is issued for it
  5. All ISAPI calls use HTTP Digest auth, accept self-signed TLS certs, retry once on timeout, and parse XML responses
**Plans**: 3 plans

Plans:
- [x] 02-01-PLAN.md — Extend ISAPIClient with detection GET/PUT methods and timeout retry logic
- [x] 02-02-PLAN.md — Disarm operation: NVR pre-check, snapshot, refcount increment, parallel ISAPI writes
- [x] 02-03-PLAN.md — Arm operation: refcount decrement, conditional restore, snapshot deletion

### Phase 3: Partition API
**Goal**: Operators can fully manage partitions via REST API and external VMS can query partition state and trigger arm/disarm
**Depends on**: Phase 2
**Requirements**: PART-01, PART-02, PART-03, PART-04, PART-05, API-01, API-02, API-03, API-04, API-05, API-06, API-07, API-08, API-09
**Success Criteria** (what must be TRUE):
  1. Operator can create, list, retrieve detail, update, and delete partitions via REST — delete is blocked while partition is disarmed
  2. GET /api/partitions/{id}/state returns per-camera detection status including which partitions are currently disarming each camera
  3. GET /api/dashboard returns all partitions with disarmed duration and an alert flag for overdue partitions
  4. All endpoints return the standard envelope `{ success, data, error }` and invalid input returns 422 with a clear message
  5. GET /api/partitions/{id}/audit returns the last 20 entries with pagination support
**Plans**: TBD

Plans:
- [x] 03-01: Partition CRUD (create, list, detail, update, delete with guard)
- [ ] 03-02: REST API surface (all routes, envelope, validation, audit and state endpoints)
- [ ] 03-03: Dashboard and location/NVR API endpoints

### Phase 4: Automation & Alerts
**Goal**: The system automatically rearms partitions on schedule, alerts on stuck-disarmed conditions, and alerts on NVR connectivity loss — without any manual trigger
**Depends on**: Phase 3
**Requirements**: JOB-01, JOB-02, JOB-03, ALRT-01, ALRT-02, ALRT-03
**Success Criteria** (what must be TRUE):
  1. A partition disarmed with auto_rearm_minutes set is automatically armed at the scheduled time with performed_by='system:auto_rearm' and sends the auto_rearmed webhook
  2. A partition disarmed past its alert_if_disarmed_minutes threshold triggers a stuck_disarmed webhook every 5 minutes until rearmed
  3. When an NVR transitions from online to offline, the NVR offline webhook fires within 60 seconds
  4. Manually arming a partition before its scheduled rearm time cancels the pending rearm job
**Plans**: 2 plans

Plans:
- [ ] 04-01-PLAN.md — APScheduler setup, auto-rearm job with webhook, and job cancellation on manual arm
- [ ] 04-02-PLAN.md — Stuck-disarmed monitor, NVR health check, and monitor registration into lifespan

### Phase 5: Admin UI
**Goal**: Operators can monitor all partition states, trigger arm/disarm with confirmation, edit partitions, and manage NVRs through a web browser — with no page refresh needed for status updates
**Depends on**: Phase 3
**Requirements**: UI-01, UI-02, UI-03, UI-04
**Success Criteria** (what must be TRUE):
  1. Dashboard page auto-refreshes every 10 seconds and highlights any partition that is overdue for rearm
  2. Partition detail page shows per-camera detection status, a countdown to auto-rearm, and the last 20 audit entries without a full page reload
  3. ARM and DISARM buttons on the dashboard and detail pages show a confirmation modal before sending the request
  4. NVR management page allows adding an NVR and testing connectivity inline via HTMX without navigating away
**Plans**: 2 plans

Plans:
- [ ] 05-01-PLAN.md — Dashboard page and partition detail page (HTMX polling, state badges, modals)
- [ ] 05-02-PLAN.md — Partition create/edit page and NVR management page

### Phase 6: Infrastructure
**Goal**: The entire service starts with `docker compose up`, produces structured logs, shuts down cleanly, and any developer can understand it from the README alone
**Depends on**: Phase 5
**Requirements**: INFRA-01, INFRA-02, INFRA-03, INFRA-04, INFRA-05, INFRA-06, INFRA-07
**Success Criteria** (what must be TRUE):
  1. `docker compose up` on a fresh machine with only a populated .env starts the service with no manual steps
  2. Every log line is valid JSON containing timestamp, level, request_id, and component fields; NVR passwords never appear in logs
  3. Sending SIGTERM to the container lets in-flight ISAPI calls finish before the process exits
  4. README.md enables a new operator to set up and integrate the service using only its contents
**Plans**: TBD

Plans:
- [ ] 06-01: Dockerfile, docker-compose.yml, .env.example, and health checks
- [ ] 06-02: Structured JSON logging, graceful shutdown, parameterized queries audit, and README

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | 3/3 | Complete    | 2026-03-10 |
| 2. ISAPI Core Operations | 3/3 | Complete | 2026-03-10 |
| 3. Partition API | 3/3 | Complete   | 2026-03-10 |
| 4. Automation & Alerts | 2/2 | Complete   | 2026-03-11 |
| 5. Admin UI | 2/2 | Complete   | 2026-03-11 |
| 6. Infrastructure | 0/2 | Not started | - |
