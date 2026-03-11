# Hikvision Partition Manager

Hikvision Partition Manager is a FastAPI microservice for managing virtual camera detection partitions on Hikvision NVR systems.

It lets a VMS (Video Management System) disarm and arm groups of cameras (partitions) by toggling Hikvision ISAPI Smart Detection. Cameras shared across multiple partitions are managed with refcount logic so detection is only restored when all disarming partitions have rearmed.

---

## Quick Start

### Prerequisites

- Docker and Docker Compose v2
- Python 3.12 (for local development without Docker)

### Setup (3 steps)

**Step 1 — Clone and configure**

```bash
git clone https://github.com/your-org/hikvision-partition-manager.git
cd hikvision-partition-manager
cp .env.example .env
# Edit .env and fill in DATABASE_URL, ENCRYPTION_KEY, and any optional values
```

**Step 2 — Start services**

```bash
docker compose up
```

This starts PostgreSQL and the application. Alembic migrations run automatically on startup. The app waits for Postgres to be healthy before starting.

**Step 3 — Open the dashboard**

```
http://localhost:8000
```

You will see the partition dashboard. Add NVRs under the NVR Management page, then create partitions and assign cameras.

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | Yes | — | PostgreSQL connection string. Format: `postgresql+asyncpg://user:pass@host:5432/dbname` |
| `ENCRYPTION_KEY` | Yes | — | Fernet key for NVR password encryption at rest. Generate with: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `BASE_URL` | No | `http://localhost:8000` | Public base URL of the service. Used in webhook payloads and alert links. |
| `LOG_LEVEL` | No | `INFO` | Logging verbosity. Options: `DEBUG`, `INFO`, `WARNING`, `ERROR`. All output is JSON-formatted. |
| `ALERT_WEBHOOK_URL` | No | — | HTTP POST endpoint for alert notifications (stuck-disarmed, NVR offline, auto-rearm fired). |
| `POLL_INTERVAL_SECONDS` | No | `300` | Interval in seconds for the stuck-disarmed monitor job (default: 5 minutes). |

---

## VMS Integration Guide

This guide is for security integrators connecting an existing VMS to control partitions.

### Workflow

When an alarm fires and cameras should stop detecting:

1. **Disarm the partition** — POST to disarm endpoint with the identity of the disarming system
2. **Monitor state** — poll the partition state endpoint to confirm cameras are disabled
3. **Rearm when event clears** — POST to arm endpoint to restore camera detection

### API Examples

Replace `http://localhost:8000` with your `BASE_URL` value.

**Disarm a partition (alarm fires)**

```bash
curl -X POST http://localhost:8000/api/partitions/{partition_id}/disarm \
  -H "Content-Type: application/json" \
  -d '{"disarmed_by": "vms-system-1", "auto_rearm_minutes": 30}'
```

`auto_rearm_minutes` is optional. If provided, the partition auto-rearms after that many minutes.

**Arm a partition (event clears)**

```bash
curl -X POST http://localhost:8000/api/partitions/{partition_id}/arm \
  -H "Content-Type: application/json" \
  -d '{"armed_by": "vms-system-1"}'
```

**Get partition state**

```bash
curl http://localhost:8000/api/partitions/{partition_id}/state
```

Response includes: `state` (armed/disarmed/partial), `disarmed_by_partitions`, `cameras` with per-camera status, and `scheduled_rearm_at` if auto-rearm is pending.

**Get dashboard summary**

```bash
curl http://localhost:8000/api/dashboard
```

Returns all partitions with their current state, overdue status, and camera counts.

### Partition and Camera IDs

Use the dashboard API or the web UI at `http://localhost:8000` to find partition UUIDs. Partitions are identified by UUID in all API calls.

---

## Refcount Logic

When a camera belongs to more than one partition, disarming one partition should not restore detection — the camera must stay disabled until all partitions that disarmed it have rearmed.

```
Camera C belongs to partitions P1 and P2

Disarm P1: refcount[C] = [P1]       → C detection disabled
Disarm P2: refcount[C] = [P1, P2]   → C stays disabled

Arm P1:    refcount[C] = [P2]        → C stays disabled (P2 still disarmed)
Arm P2:    refcount[C] = []          → C detection RESTORED
```

### Edge Cases

**Idempotent disarm:** If a partition is already disarmed by the same VMS identity, disarming again is a no-op. The refcount is not incremented twice for the same disarming identity.

**Partial state:** If some cameras in a partition fail their ISAPI call (e.g. NVR unreachable), the partition enters `partial` state. The successfully toggled cameras retain their new state. The operator can retry by calling arm or disarm again.

---

## Troubleshooting

**NVR not connecting**

Check that the NVR IP, port, username, and password are correct in the NVR Management page. The service accepts self-signed TLS certificates by default (NVRs commonly use them). Verify the NVR is reachable from the Docker container: `docker compose exec app curl -k https://<nvr-ip>/ISAPI/System/deviceInfo`

**Webhooks not firing**

Check that `ALERT_WEBHOOK_URL` is set in your `.env` file and that the URL is reachable from the Docker container. Test with: `docker compose exec app curl -X POST $ALERT_WEBHOOK_URL -d '{"test":true}'`

**Arm not restoring detection**

A camera may belong to another disarmed partition. Check `GET /api/partitions/{id}/state` and look at `disarmed_by_partitions` in the camera list — if another partition is listed, that partition must be armed first before detection is restored.

**Auto-rearm did not fire**

Set `LOG_LEVEL=DEBUG` in `.env` and restart with `docker compose up`. Look for `auto_rearm` events in the JSON logs. Verify the `scheduled_rearm_at` field is set by calling `GET /api/partitions/{id}/state`. If it is null, no auto-rearm was scheduled — check whether `auto_rearm_minutes` was included in the disarm request.

**Migration fails on startup**

Check that `DATABASE_URL` uses the asyncpg driver format: `postgresql+asyncpg://user:pass@host:5432/dbname`. The plain `postgresql://` format will cause a connection error. If using Docker Compose, ensure the `db` service is healthy before the app starts (the compose file handles this automatically via `depends_on: condition: service_healthy`).
