import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from typing import Generic, TypeVar, Optional, List, Any, Dict

T = TypeVar("T")

# ---------------------------------------------------------------------------
# Arm / Disarm schemas (pre-existing)
# ---------------------------------------------------------------------------

class PartitionError(BaseModel):
    camera_id: uuid.UUID
    http_status: Optional[int] = None
    message: str

class DisarmRequest(BaseModel):
    disarmed_by: str
    reason: Optional[str] = None

class DisarmResponse(BaseModel):
    cameras_disarmed: int
    cameras_kept_disarmed_by_other_partition: int
    scheduled_rearm_at: Optional[datetime] = None
    errors: List[PartitionError] = []

class ArmRequest(BaseModel):
    armed_by: str

class ArmResponse(BaseModel):
    cameras_restored: int
    cameras_kept_disarmed: int
    errors: List[PartitionError] = []

# ---------------------------------------------------------------------------
# CRUD schemas
# ---------------------------------------------------------------------------

class PartitionCreate(BaseModel):
    name: str
    description: Optional[str] = None
    location_id: Optional[uuid.UUID] = None
    auto_rearm_minutes: Optional[int] = None
    alert_if_disarmed_minutes: Optional[int] = None
    camera_ids: List[uuid.UUID] = []


class PartitionUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    auto_rearm_minutes: Optional[int] = None
    alert_if_disarmed_minutes: Optional[int] = None


class CameraRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    channel_no: int
    name: Optional[str] = None
    nvr_id: uuid.UUID
    nvr_name: Optional[str] = None
    nvr_ip: Optional[str] = None


class PartitionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: Optional[str] = None
    location_id: Optional[uuid.UUID] = None
    auto_rearm_minutes: Optional[int] = None
    alert_if_disarmed_minutes: Optional[int] = None
    state: Optional[str] = None
    created_at: datetime


class PartitionDetail(PartitionRead):
    """Extended read schema that includes member cameras with NVR info."""
    cameras: List[CameraRead] = []


class PartitionCameraSync(BaseModel):
    """Replace camera membership for a partition."""
    camera_ids: List[uuid.UUID]


# ---------------------------------------------------------------------------
# State endpoint schemas
# ---------------------------------------------------------------------------

class CameraStateRead(BaseModel):
    """Per-camera detection status inside PartitionStateRead."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    channel_no: int
    name: Optional[str] = None
    nvr_id: uuid.UUID
    # Detection types currently enabled in the ISAPI snapshot, keyed by detection type.
    # None if no snapshot exists (camera is in armed state with no disarm recorded).
    detection_snapshot: Optional[Dict[str, Any]] = None
    # Refcount: list of partition UUIDs that have disarmed this camera.
    disarmed_by_partitions: List[uuid.UUID] = []
    disarm_count: int = 0


class PartitionStateRead(BaseModel):
    """Deep-dive state for a partition: overall state + per-camera detection status & refcounts."""
    model_config = ConfigDict(from_attributes=True)

    partition_id: uuid.UUID
    state: Optional[str] = None
    last_changed_at: Optional[datetime] = None
    last_changed_by: Optional[str] = None
    scheduled_rearm_at: Optional[datetime] = None
    error_detail: Optional[str] = None
    cameras: List[CameraStateRead] = []


# ---------------------------------------------------------------------------
# Audit log schemas
# ---------------------------------------------------------------------------

class AuditLogEntryRead(BaseModel):
    """Single audit log entry."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    partition_id: uuid.UUID
    action: str
    performed_by: str
    audit_metadata: Optional[Dict[str, Any]] = None
    created_at: datetime


class PaginatedAuditLog(BaseModel):
    """Paginated audit log response with metadata."""
    total: int
    limit: int
    offset: int
    items: List[AuditLogEntryRead]


# ---------------------------------------------------------------------------
# Dashboard schemas
# ---------------------------------------------------------------------------

class DashboardPartitionEntry(BaseModel):
    """Summary entry for a single partition on the dashboard."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: Optional[str] = None
    location_id: Optional[uuid.UUID] = None
    state: Optional[str] = None
    # How many minutes the partition has been disarmed (None if not disarmed).
    disarmed_minutes: Optional[float] = None
    # True when alert_if_disarmed_minutes is set and threshold has been exceeded.
    overdue: bool = False
    scheduled_rearm_at: Optional[datetime] = None
    last_changed_at: Optional[datetime] = None
    last_changed_by: Optional[str] = None


class DashboardResponse(BaseModel):
    """Aggregated dashboard view of all non-deleted partitions."""
    partitions: List[DashboardPartitionEntry]
    total: int
    active_count: int  # partitions in error / partial / disarmed state
