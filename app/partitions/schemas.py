import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from typing import Generic, TypeVar, Optional, List

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
