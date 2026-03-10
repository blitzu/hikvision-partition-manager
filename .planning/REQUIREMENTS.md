# Requirements: Virtual Partition Management System

**Defined:** 2026-03-10
**Core Value:** Disarming a partition disables detection on all member cameras via ISAPI; arming restores exact saved state, respecting multi-partition refcount logic.

## v1 Requirements

### Data Model

- [x] **DATA-01**: System stores locations with name and timezone
- [x] **DATA-02**: System stores NVR devices linked to a location, with encrypted password, IP, port, model, status
- [x] **DATA-03**: System stores cameras linked to an NVR with channel number and enabled flag; (nvr_id, channel_no) is unique
- [x] **DATA-04**: System stores virtual partitions with name, description, auto_rearm_minutes, alert_if_disarmed_minutes
- [x] **DATA-05**: System stores partition-camera membership (many-to-many)
- [x] **DATA-06**: System stores partition_state per partition: state enum (armed/disarmed/error/partial), last_changed_at, last_changed_by, scheduled_rearm_at, error_detail
- [x] **DATA-07**: System stores camera_detection_snapshot per camera per partition: full JSONB of ISAPI XML response, taken_at
- [x] **DATA-08**: System stores camera_disarm_refcount per camera: array of partition_ids currently disarming, generated count column
- [x] **DATA-09**: System stores partition_audit_log entries: partition_id, action, performed_by, metadata JSONB, created_at

### NVR & Camera Management

- [x] **NVR-01**: Operator can create a location (name, timezone)
- [x] **NVR-02**: Operator can add an NVR device to a location (name, IP, port, username, password); password stored encrypted
- [x] **NVR-03**: Operator can test NVR connectivity via API; returns deviceInfo on success
- [x] **NVR-04**: Operator can sync cameras from an NVR by fetching live channel list via ISAPI and upserting into cameras table
- [x] **NVR-05**: System updates nvr_devices.last_seen_at and status on every successful ISAPI contact
- [x] **NVR-06**: NVR passwords are never written to logs or API responses

### Virtual Partition CRUD

- [ ] **PART-01**: Operator can create a partition with name, description, timers, and an initial list of camera_ids
- [ ] **PART-02**: Operator can list all partitions with their current state
- [ ] **PART-03**: Operator can retrieve partition detail: cameras (with NVR info), state, per-camera refcount, last 20 audit entries
- [ ] **PART-04**: Operator can update a partition's name, description, timers, and camera membership
- [ ] **PART-05**: Operator can delete a partition only when its state is armed

### Disarm Operation

- [ ] **DARM-01**: External VMS can POST disarm with disarmed_by and optional reason
- [ ] **DARM-02**: Before disarming, system checks connectivity of all involved NVRs; on failure, sets state=error and returns error
- [ ] **DARM-03**: For each camera, system reads current detection config from all 4 ISAPI endpoints (motionDetection, LineDetection, FieldDetection, shelteralarm); saves only endpoints returning HTTP 200
- [ ] **DARM-04**: If a camera already has a snapshot (still disarmed from a prior operation), system does NOT overwrite the existing snapshot
- [ ] **DARM-05**: System disables all detection types that were enabled=true in the snapshot via PUT ISAPI, preserving all other settings
- [ ] **DARM-06**: System adds partition_id to camera's disarmed_by_partitions array (refcount increment)
- [ ] **DARM-07**: If auto_rearm_minutes is set, system schedules a rearm job at the calculated time
- [ ] **DARM-08**: System appends audit log entry for disarm action
- [ ] **DARM-09**: Response includes cameras_disarmed count, cameras_kept_disarmed_by_other_partition count, scheduled_rearm_at, errors list
- [ ] **DARM-10**: ISAPI calls to cameras on the same NVR are executed in parallel, not sequentially

### Arm Operation

- [ ] **ARM-01**: External VMS can POST arm with armed_by
- [ ] **ARM-02**: System removes this partition_id from each camera's disarmed_by_partitions array (refcount decrement)
- [ ] **ARM-03**: For cameras where refcount reaches 0: system restores detection config from snapshot via PUT ISAPI, then deletes snapshot record
- [ ] **ARM-04**: For cameras where refcount > 0: system logs that camera stays disarmed, does NOT restore detection
- [ ] **ARM-05**: System cancels any pending scheduled rearm job for this partition
- [ ] **ARM-06**: System appends audit log entry for arm action
- [ ] **ARM-07**: Response includes cameras_restored count, cameras_kept_disarmed count, errors list

### ISAPI HTTP Client

- [ ] **ISAPI-01**: All ISAPI calls use HTTP Digest Authentication (not Basic)
- [ ] **ISAPI-02**: Connection timeout: 5 seconds; read timeout: 10 seconds
- [ ] **ISAPI-03**: On timeout, system retries once before marking camera/NVR as error
- [ ] **ISAPI-04**: System accepts self-signed TLS certificates from NVRs
- [ ] **ISAPI-05**: System parses XML responses (not JSON) from ISAPI endpoints

### Background Jobs

- [ ] **JOB-01**: Auto-rearm job fires at exact scheduled_rearm_at; calls arm logic with performed_by='system:auto_rearm'; sends webhook on completion
- [ ] **JOB-02**: Stuck-disarmed monitor runs every 5 minutes; finds partitions where disarmed duration > alert_if_disarmed_minutes; POSTs alert webhook per partition
- [ ] **JOB-03**: NVR health check runs every 60 seconds; pings all NVRs; updates status and last_seen_at; POSTs alert webhook when NVR transitions from online to offline

### Webhook Alerts

- [ ] **ALRT-01**: Auto-rearm webhook: `{ type: 'auto_rearmed', partition_id, partition_name }`
- [ ] **ALRT-02**: Stuck disarmed webhook: `{ type: 'partition_stuck_disarmed', partition_id, partition_name, disarmed_by, disarmed_at, minutes_elapsed, scheduled_rearm_at }`
- [ ] **ALRT-03**: NVR offline webhook: `{ type: 'nvr_offline', nvr_id, nvr_name, location_name }`

### REST API

- [ ] **API-01**: All responses use envelope: `{ success: bool, data: any, error: string|null }`
- [ ] **API-02**: Location CRUD endpoints (POST /api/locations, GET /api/locations, POST /api/locations/{id}/nvrs, GET /api/locations/{id}/nvrs)
- [ ] **API-03**: NVR endpoints (GET /api/nvrs/{id}/test, GET /api/nvrs/{id}/cameras/sync)
- [ ] **API-04**: Partition CRUD endpoints (POST/GET /api/partitions, GET/PATCH/DELETE /api/partitions/{id})
- [ ] **API-05**: Partition control endpoints (POST /api/partitions/{id}/disarm, POST /api/partitions/{id}/arm)
- [ ] **API-06**: Partition state endpoint (GET /api/partitions/{id}/state) with per-camera detection status
- [ ] **API-07**: Audit log endpoint (GET /api/partitions/{id}/audit?limit&offset)
- [ ] **API-08**: Dashboard endpoint (GET /api/dashboard) with all partitions, disarmed duration, alert flag
- [ ] **API-09**: All endpoints validate input and return 422 with clear error messages on invalid input

### Admin UI

- [ ] **UI-01**: Dashboard page (/) — table of all partitions with state badge, disarmed duration, alert highlight, ARM/DISARM quick buttons with confirmation modal; auto-refreshes every 10 seconds via HTMX
- [ ] **UI-02**: Partition detail page (/partitions/{id}) — state, camera list with detection status, ARM/DISARM button with impact modal, auto-rearm countdown, last 20 audit entries, inline edit form
- [ ] **UI-03**: Partition create/edit page (/partitions/new, /partitions/{id}/edit) — name/description/timers fields, camera selector grouped by NVR with per-NVR sync button
- [ ] **UI-04**: NVR management page (/nvrs) — list NVRs with status badge, add NVR form, test connectivity button (inline HTMX result), last seen timestamp

### Infrastructure & Code Quality

- [ ] **INFRA-01**: docker-compose.yml with app + postgres services, volume for data persistence, health checks; starts with zero manual steps
- [ ] **INFRA-02**: Multi-stage Dockerfile, non-root user, minimal image
- [ ] **INFRA-03**: .env.example with all required variables: DATABASE_URL, ENCRYPTION_KEY, ALERT_WEBHOOK_URL, POLL_INTERVAL_SECONDS, LOG_LEVEL, BASE_URL
- [ ] **INFRA-04**: README.md with 3-step setup, env vars table, API curl examples, VMS integration guide, refcount logic explanation
- [ ] **INFRA-05**: Structured JSON logging with timestamp, level, request_id, component fields
- [ ] **INFRA-06**: Graceful shutdown: complete in-flight ISAPI calls before exit
- [ ] **INFRA-07**: All database queries parameterized (no string interpolation)

## v2 Requirements

### Enhanced Features

- **V2-01**: OAuth / API key authentication layer
- **V2-02**: Multi-user audit trail with user identity from auth layer
- **V2-03**: Camera health monitoring (detect cameras that stop reporting after detection re-enable)
- **V2-04**: Partition scheduling (recurring arm/disarm schedules based on time-of-day)
- **V2-05**: Email notifications in addition to webhooks

## Out of Scope

| Feature | Reason |
|---------|--------|
| Authentication / authorization | External auth layer added later (v2) |
| Event processing / forwarding | Not this service's job; existing pipeline untouched |
| LanController / Moxa IO integration | Different subsystem |
| Mobile app | Web-first admin UI only |
| Email notifications | Webhooks only per spec |
| Event storage / logging | Not this service's responsibility |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| DATA-01 | Phase 1 | Complete |
| DATA-02 | Phase 1 | Complete |
| DATA-03 | Phase 1 | Complete |
| DATA-04 | Phase 1 | Complete |
| DATA-05 | Phase 1 | Complete |
| DATA-06 | Phase 1 | Complete |
| DATA-07 | Phase 1 | Complete |
| DATA-08 | Phase 1 | Complete |
| DATA-09 | Phase 1 | Complete |
| NVR-01 | Phase 1 | Complete |
| NVR-02 | Phase 1 | Complete |
| NVR-03 | Phase 1 | Complete |
| NVR-04 | Phase 1 | Complete |
| NVR-05 | Phase 1 | Complete |
| NVR-06 | Phase 1 | Complete |
| ISAPI-01 | Phase 2 | Pending |
| ISAPI-02 | Phase 2 | Pending |
| ISAPI-03 | Phase 2 | Pending |
| ISAPI-04 | Phase 2 | Pending |
| ISAPI-05 | Phase 2 | Pending |
| DARM-01 | Phase 2 | Pending |
| DARM-02 | Phase 2 | Pending |
| DARM-03 | Phase 2 | Pending |
| DARM-04 | Phase 2 | Pending |
| DARM-05 | Phase 2 | Pending |
| DARM-06 | Phase 2 | Pending |
| DARM-07 | Phase 2 | Pending |
| DARM-08 | Phase 2 | Pending |
| DARM-09 | Phase 2 | Pending |
| DARM-10 | Phase 2 | Pending |
| ARM-01 | Phase 2 | Pending |
| ARM-02 | Phase 2 | Pending |
| ARM-03 | Phase 2 | Pending |
| ARM-04 | Phase 2 | Pending |
| ARM-05 | Phase 2 | Pending |
| ARM-06 | Phase 2 | Pending |
| ARM-07 | Phase 2 | Pending |
| PART-01 | Phase 3 | Pending |
| PART-02 | Phase 3 | Pending |
| PART-03 | Phase 3 | Pending |
| PART-04 | Phase 3 | Pending |
| PART-05 | Phase 3 | Pending |
| API-01 | Phase 3 | Pending |
| API-02 | Phase 3 | Pending |
| API-03 | Phase 3 | Pending |
| API-04 | Phase 3 | Pending |
| API-05 | Phase 3 | Pending |
| API-06 | Phase 3 | Pending |
| API-07 | Phase 3 | Pending |
| API-08 | Phase 3 | Pending |
| API-09 | Phase 3 | Pending |
| JOB-01 | Phase 4 | Pending |
| JOB-02 | Phase 4 | Pending |
| JOB-03 | Phase 4 | Pending |
| ALRT-01 | Phase 4 | Pending |
| ALRT-02 | Phase 4 | Pending |
| ALRT-03 | Phase 4 | Pending |
| UI-01 | Phase 5 | Pending |
| UI-02 | Phase 5 | Pending |
| UI-03 | Phase 5 | Pending |
| UI-04 | Phase 5 | Pending |
| INFRA-01 | Phase 6 | Pending |
| INFRA-02 | Phase 6 | Pending |
| INFRA-03 | Phase 6 | Pending |
| INFRA-04 | Phase 6 | Pending |
| INFRA-05 | Phase 6 | Pending |
| INFRA-06 | Phase 6 | Pending |
| INFRA-07 | Phase 6 | Pending |

**Coverage:**
- v1 requirements: 68 total
- Mapped to phases: 68
- Unmapped: 0

---
*Requirements defined: 2026-03-10*
*Last updated: 2026-03-10 after roadmap creation*
