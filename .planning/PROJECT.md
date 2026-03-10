# Virtual Partition Management System

## What This Is

A standalone microservice that manages "virtual partitions" for Hikvision NVR cameras.
It enables and disables motion/intrusion detection on specific cameras via Hikvision ISAPI
when a partition is armed or disarmed. The service is a component in a larger physical
security SaaS platform and must remain completely transparent to the existing event pipeline.

## Core Value

When a partition is disarmed, every camera in it must have ALL active detection types
disabled via ISAPI within one operation — and when rearmed, detection must be restored
to exactly the saved snapshot state, respecting multi-partition camera membership.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Virtual partitions (named groups of cameras) can be created, edited, and deleted
- [ ] Cameras can span multiple NVR devices and multiple partitions simultaneously
- [ ] DISARM: reads + saves detection config snapshot per camera, then disables all active detection types via ISAPI
- [ ] ARM: restores detection config from snapshot only for cameras with refcount=0
- [ ] Camera disarm reference count: camera stays disarmed until ALL partitions containing it are armed
- [ ] HTTP Digest Authentication for all ISAPI calls
- [ ] NVR passwords encrypted at rest (AES with ENCRYPTION_KEY)
- [ ] Auto-rearm: scheduled rearm fires at `scheduled_rearm_at` via background job
- [ ] Stuck disarmed monitor: alert webhook fires every 5 min for overdue partitions
- [ ] NVR health check: connectivity check every 60 seconds, alert on status change
- [ ] REST API for external VMS integration (disarm/arm/state endpoints)
- [ ] Admin UI: dashboard, partition detail, partition editor, NVR management (HTMX + Jinja2 + Pico CSS)
- [ ] Docker Compose deployment (app + postgres, zero manual steps)

### Out of Scope

- Authentication/authorization — external auth layer will be added later
- Event processing, forwarding or storage of camera motion events
- LanController or Moxa IO hardware integration
- Mobile app
- Email notifications (webhooks only)

## Context

- **Platform context**: This service plugs into an existing physical security SaaS platform.
  The existing event pipeline must remain completely unaware of this service.
- **Suppression mechanism**: NVRs stop generating events naturally when detection is disabled.
  This service only sends ISAPI configuration commands — it does not intercept or filter events.
- **ISAPI quirks**: Hikvision NVRs use HTTP Digest auth, self-signed TLS certs (must accept),
  and return XML (not JSON). Not all detection types are supported by all camera models.
- **Detection types managed**: motionDetection, LineDetection, FieldDetection, shelteralarm
- **Snapshot immutability**: If a camera is already disarmed (has a snapshot), do NOT overwrite
  the snapshot on a subsequent disarm — keep the original armed-state snapshot.

## Constraints

- **Tech Stack**: Python 3.12 + FastAPI, PostgreSQL 16, APScheduler, httpx (digest auth), Jinja2 + HTMX + Pico CSS
- **Auth**: HTTP Digest only for ISAPI (Hikvision does not support Basic auth reliably)
- **Timeouts**: ISAPI connection=5s, read=10s; retry once on timeout before marking error
- **TLS**: Must accept self-signed certificates from NVRs
- **Security**: NVR passwords never logged, encrypted at rest with ENCRYPTION_KEY (32-byte)
- **Parallelism**: ISAPI calls to cameras on the same NVR must be parallelized, not sequential
- **Graceful shutdown**: Complete in-flight ISAPI calls before exit

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Python + FastAPI | Async-native, best XML/digest-auth HTTP ecosystem | — Pending |
| APScheduler (in-process) | No separate scheduler process needed for this scale | — Pending |
| PostgreSQL native arrays for refcount | `disarmed_by_partitions uuid[]` + generated count column | — Pending |
| JSONB for detection snapshots | Flexible storage for heterogeneous ISAPI XML responses | — Pending |
| HTMX + Jinja2 + Pico CSS | Specified; avoids SPA complexity for internal admin | — Pending |
| No external message queue | APScheduler sufficient; Celery would add operational overhead | — Pending |

---
*Last updated: 2026-03-10 after initialization*
