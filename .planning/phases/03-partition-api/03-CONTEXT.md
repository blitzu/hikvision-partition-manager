# Phase 3: Partition API - Context

**Gathered:** 2026-03-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Operators can fully manage partitions via REST API and external VMS can query partition state and trigger arm/disarm. Covers: Partition CRUD (create, list, detail, update, soft-delete), Partition camera membership management (sync/replace strategy), Partition state endpoint (per-camera status), and Paginated Audit Log.

</domain>

<decisions>
## Implementation Decisions

### Partition Management (CRUD)
- **Camera Assignment**: Separate from initial creation. Partitions are created "empty" (or with basic metadata), and cameras are assigned via a dedicated sync/replace endpoint.
- **Sync Strategy**: "Replace" (Full Sync). Sending a list of `camera_ids` to the partition's camera endpoint replaces the existing membership entirely.
- **Validation**: Strict. If any provided `camera_id` is invalid or does not exist, the entire update/assignment request fails (422 Unprocessable Entity).
- **Location Bound**: Enforced. A partition belongs to exactly one Location. All cameras added to a partition must belong to NVRs within that same Location.

### Deletion Guard & Lifecycle
- **Soft Delete**: Partitions are not physically removed from the database. A `deleted_at` timestamp is used to hide them, preserving audit history and state records.
- **Deletion Blocks**: Deletion is blocked if the state is `disarmed` or `partial`.
- **Cleanup**: Deletion is allowed if the state is `error` (to allow fixing broken configs).
- **Response**: Blocked deletes return `400 Bad Request` with a detailed message: "Partiția trebuie să fie în starea ARMED sau ERROR înainte de ștergere."

### Audit Log (API-07)
- **Data Fetching**: Separate endpoint. Partition details (`GET /api/partitions/{id}`) do NOT include the audit log. It must be fetched via `/api/partitions/{id}/audit`.
- **Pagination**: Generous defaults. Default limit: 50, Maximum limit: 500.
- **Response Structure**: Wrapped with metadata. Includes `items`, `total`, `page`, `size`, and `has_more`.
- **Sorting**: Reverse chronological (Newest first) by default.

### Dashboard (API-08)
- **Duration Calculation**: Dynamic. Disarmed duration is calculated by the API at request time based on `last_changed_at`.
- **Alert Flag**: Combined trigger. Flag is active if `alert_if_disarmed_minutes` is exceeded OR if `scheduled_rearm_at` has passed.
- **Detail Level**: Detailed. The dashboard returns a summary of partitions including a list/count of member cameras for quick status overview.
- **Default View**: Show all partitions, but sorted by state (Non-armed/Active partitions first: `error`, `partial`, `disarmed`, then `armed`).

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/partitions/models.py`: `Partition`, `PartitionCamera`, `PartitionState`, `PartitionAuditLog` models are already defined.
- `app/partitions/service.py`: Contains `disarm_partition` and `arm_partition`. CRUD logic should be added here.
- `app/partitions/routes.py`: Contains disarm/arm endpoints. CRUD routes should be added here.
- `app/core/schemas.py`: `APIResponse[T]` envelope must be used for all new endpoints.

### Established Patterns
- Soft Delete: Need to add `deleted_at: Mapped[datetime | None]` to the `Partition` model and update queries to filter by `deleted_at is None`.
- Location Filtering: When syncing cameras, verify `camera.nvr.location_id == partition.location_id`.

### Integration Points
- `app/main.py`: `partitions_router` is already included.
- `app/partitions/schemas.py`: `PartitionRead`, `PartitionCreate`, `PartitionUpdate` schemas need to be defined.

</code_context>

<deferred>
## Deferred Ideas

- None — discussion stayed within phase scope.

</deferred>

---

*Phase: 03-partition-api*
*Context gathered: 2026-03-10*
