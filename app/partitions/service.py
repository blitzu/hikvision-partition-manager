import uuid
import asyncio
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.partitions.models import (
    Partition,
    PartitionCamera,
    PartitionState,
    CameraDetectionSnapshot,
    CameraDisarmRefcount,
    PartitionAuditLog,
)
from app.cameras.models import Camera
from app.nvrs.models import NVRDevice
from app.isapi.client import ISAPIClient
from app.core.crypto import decrypt_password
from app.jobs.auto_rearm import cancel_rearm, schedule_rearm
from app.partitions.schemas import (
    DisarmResponse,
    ArmResponse,
    PartitionError,
    PartitionCreate,
    PartitionUpdate,
    PartitionRead,
    PartitionDetail,
    CameraRead,
    CameraStateRead,
    PartitionStateRead,
    AuditLogEntryRead,
    PaginatedAuditLog,
    DashboardPartitionEntry,
    DashboardResponse,
)


DETECTION_TYPES = [
    "MotionDetection",
    "LineDetection",
    "FieldDetection",
    "shelteralarm",
]


def _is_enabled_in_xml(xml_text: str) -> bool:
    """Check if the 'enabled' element in the XML is set to 'true'."""
    try:
        root = ET.fromstring(xml_text)
        for el in root.iter():
            if el.tag.split("}")[-1] == "enabled":
                return el.text.lower() == "true"
    except Exception:
        pass
    return False


def _disable_in_xml(xml_text: str) -> str:
    """Set the 'enabled' element in the XML to 'false'."""
    root = ET.fromstring(xml_text)
    for el in root.iter():
        if el.tag.split("}")[-1] == "enabled":
            el.text = "false"
            break
    return ET.tostring(root, encoding="unicode")


async def disarm_partition(
    partition_id: uuid.UUID,
    disarmed_by: str,
    reason: Optional[str],
    db: AsyncSession,
) -> DisarmResponse:
    # 1. Load partition
    partition = await db.get(Partition, partition_id)
    if not partition:
        raise HTTPException(status_code=404, detail="Partition not found")

    # 2. Load or create PartitionState
    stmt = select(PartitionState).where(PartitionState.partition_id == partition_id)
    result = await db.execute(stmt)
    state = result.scalar_one_or_none()
    if not state:
        state = PartitionState(partition_id=partition_id, state="armed")
        db.add(state)

    # 3. Idempotency check
    if state.state == "disarmed":
        return DisarmResponse(
            cameras_disarmed=0,
            cameras_kept_disarmed_by_other_partition=0,
            scheduled_rearm_at=state.scheduled_rearm_at,
        )

    # 4. Load all cameras in partition
    stmt = (
        select(Camera)
        .join(PartitionCamera, Camera.id == PartitionCamera.camera_id)
        .where(PartitionCamera.partition_id == partition_id)
    )
    result = await db.execute(stmt)
    cameras = result.scalars().all()

    if not cameras:
        state.state = "disarmed"
        state.last_changed_at = datetime.now(timezone.utc)
        state.last_changed_by = disarmed_by
        if partition.auto_rearm_minutes:
            state.scheduled_rearm_at = state.last_changed_at + timedelta(minutes=partition.auto_rearm_minutes)
        else:
            state.scheduled_rearm_at = None
        audit = PartitionAuditLog(
            partition_id=partition_id,
            action="disarm",
            performed_by=disarmed_by,
            audit_metadata={"reason": reason, "cameras_disarmed": 0, "cameras_kept_disarmed_by_other_partition": 0, "errors_count": 0},
        )
        db.add(audit)
        await db.commit()
        if state.scheduled_rearm_at is not None:
            await schedule_rearm(partition_id, state.scheduled_rearm_at)
        return DisarmResponse(
            cameras_disarmed=0,
            cameras_kept_disarmed_by_other_partition=0,
            scheduled_rearm_at=state.scheduled_rearm_at,
        )

    # 5. Load all NVRs for those cameras
    nvr_ids = {c.nvr_id for c in cameras}
    stmt = select(NVRDevice).where(NVRDevice.id.in_(nvr_ids))
    result = await db.execute(stmt)
    nvrs = {n.id: n for n in result.scalars().all()}

    # NVR pre-check
    nvr_clients = {}
    for nvr_id, nvr in nvrs.items():
        password = decrypt_password(nvr.password_encrypted)
        client = ISAPIClient(nvr.ip_address, nvr.port, nvr.username, password)
        try:
            await client.get_device_info()
            nvr.status = "online"
            nvr.last_seen_at = datetime.now(timezone.utc)
            nvr_clients[nvr_id] = client
        except Exception as e:
            state.state = "error"
            state.error_detail = f"NVR {nvr.ip_address} unreachable: {str(e)}"
            state.last_changed_at = datetime.now(timezone.utc)
            state.last_changed_by = disarmed_by
            
            # Audit log for failure
            audit = PartitionAuditLog(
                partition_id=partition_id,
                action="disarm_failed",
                performed_by=disarmed_by,
                audit_metadata={"reason": reason, "error": state.error_detail},
            )
            db.add(audit)
            await db.commit()
            
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail=state.error_detail)

    # 6. Per camera, in parallel grouped by nvr_id
    errors = []
    cameras_disarmed = 0
    cameras_kept_disarmed_by_other_partition = 0
    db_lock = asyncio.Lock()

    async def process_camera(camera: Camera):
        nonlocal cameras_disarmed, cameras_kept_disarmed_by_other_partition
        client = nvr_clients[camera.nvr_id]
        
        try:
            # a. Check if snapshot exists
            async with db_lock:
                stmt = select(CameraDetectionSnapshot).where(
                    CameraDetectionSnapshot.camera_id == camera.id,
                    CameraDetectionSnapshot.partition_id == partition_id,
                )
                res = await db.execute(stmt)
                snapshot = res.scalar_one_or_none()
            
            if not snapshot:
                # b. GET all 4 detection types
                snapshot_data = {}
                found_any = False
                for d_type in DETECTION_TYPES:
                    try:
                        xml = await client.get_detection_config(camera.channel_no, d_type)
                        snapshot_data[d_type] = xml
                        found_any = True
                    except Exception:
                        # Skip if camera doesn't support it or other error
                        continue
                
                if not found_any:
                    raise Exception("Could not retrieve any detection configuration from camera")
                
                # c. Insert snapshot
                async with db_lock:
                    # DARM-04: If ANY snapshot exists for this camera, use it 
                    # (it contains the original armed state).
                    stmt = select(CameraDetectionSnapshot).where(
                        CameraDetectionSnapshot.camera_id == camera.id
                    ).limit(1)
                    res = await db.execute(stmt)
                    existing_any = res.scalar_one_or_none()
                    
                    final_snapshot_data = existing_any.snapshot_data if existing_any else snapshot_data

                    snapshot = CameraDetectionSnapshot(
                        camera_id=camera.id,
                        partition_id=partition_id,
                        snapshot_data=final_snapshot_data,
                    )
                    db.add(snapshot)
                    snapshot_data = final_snapshot_data # Use the original for subsequent PUTs
            else:
                snapshot_data = snapshot.snapshot_data

            # d. PUT modified XML to disable
            for d_type, xml in snapshot_data.items():
                if _is_enabled_in_xml(xml):
                    new_xml = _disable_in_xml(xml)
                    await client.put_detection_config(camera.channel_no, d_type, new_xml)

            # e. Update refcount
            async with db_lock:
                stmt = select(CameraDisarmRefcount).where(CameraDisarmRefcount.camera_id == camera.id)
                res = await db.execute(stmt)
                refcount = res.scalar_one_or_none()
                if not refcount:
                    refcount = CameraDisarmRefcount(camera_id=camera.id, disarmed_by_partitions=[])
                    db.add(refcount)
                
                if partition_id not in refcount.disarmed_by_partitions:
                    new_partitions = list(refcount.disarmed_by_partitions)
                    new_partitions.append(partition_id)
                    refcount.disarmed_by_partitions = new_partitions
                
                # Count logic
                if len(refcount.disarmed_by_partitions) > 1:
                    cameras_kept_disarmed_by_other_partition += 1
                else:
                    cameras_disarmed += 1

        except Exception as e:
            errors.append(PartitionError(camera_id=camera.id, message=str(e)))

    # Run all cameras in parallel
    await asyncio.gather(*(process_camera(c) for c in cameras))

    # 7. Determine final state
    if not errors:
        state.state = "disarmed"
    elif len(errors) < len(cameras):
        state.state = "partial"
    else:
        state.state = "error"
        state.error_detail = f"Failed to disarm {len(errors)} cameras"

    # 8. Update PartitionState metadata
    state.last_changed_at = datetime.now(timezone.utc)
    state.last_changed_by = disarmed_by
    
    # 9. Scheduled rearm
    if partition.auto_rearm_minutes:
        state.scheduled_rearm_at = state.last_changed_at + timedelta(minutes=partition.auto_rearm_minutes)
    else:
        state.scheduled_rearm_at = None

    # 10. Audit log
    audit = PartitionAuditLog(
        partition_id=partition_id,
        action="disarm",
        performed_by=disarmed_by,
        audit_metadata={
            "reason": reason,
            "cameras_disarmed": cameras_disarmed,
            "cameras_kept_disarmed_by_other_partition": cameras_kept_disarmed_by_other_partition,
            "errors_count": len(errors),
        },
    )
    db.add(audit)

    # 11. Commit and return
    await db.commit()

    # 12. Schedule auto-rearm job if applicable
    if state.scheduled_rearm_at is not None:
        await schedule_rearm(partition_id, state.scheduled_rearm_at)

    return DisarmResponse(
        cameras_disarmed=cameras_disarmed,
        cameras_kept_disarmed_by_other_partition=cameras_kept_disarmed_by_other_partition,
        scheduled_rearm_at=state.scheduled_rearm_at,
        errors=errors,
    )


async def arm_partition(
    partition_id: uuid.UUID,
    armed_by: str,
    db: AsyncSession,
) -> ArmResponse:
    # 1. Load partition
    partition = await db.get(Partition, partition_id)
    if not partition:
        raise HTTPException(status_code=404, detail="Partition not found")

    # Cancel any pending auto-rearm job before DB writes — done unconditionally
    # so even a failed or idempotent arm clears the scheduled job.
    await cancel_rearm(partition_id)

    # 2. Load or create PartitionState
    stmt = select(PartitionState).where(PartitionState.partition_id == partition_id)
    result = await db.execute(stmt)
    state = result.scalar_one_or_none()
    if not state:
        state = PartitionState(partition_id=partition_id, state="armed")
        db.add(state)

    # Idempotency check
    if state.state == "armed":
        return ArmResponse(cameras_restored=0, cameras_kept_disarmed=0)

    # 3. Load all cameras in partition
    stmt = (
        select(Camera)
        .join(PartitionCamera, Camera.id == PartitionCamera.camera_id)
        .where(PartitionCamera.partition_id == partition_id)
    )
    result = await db.execute(stmt)
    cameras = result.scalars().all()

    if not cameras:
        state.state = "armed"
        state.last_changed_at = datetime.now(timezone.utc)
        state.last_changed_by = armed_by
        state.scheduled_rearm_at = None
        audit = PartitionAuditLog(
            partition_id=partition_id,
            action="arm",
            performed_by=armed_by,
            audit_metadata={"cameras_restored": 0, "cameras_kept_disarmed": 0, "errors_count": 0},
        )
        db.add(audit)
        await db.commit()
        return ArmResponse(cameras_restored=0, cameras_kept_disarmed=0)

    # 4. Load all NVRs for those cameras
    nvr_ids = {c.nvr_id for c in cameras}
    stmt = select(NVRDevice).where(NVRDevice.id.in_(nvr_ids))
    result = await db.execute(stmt)
    nvrs = {n.id: n for n in result.scalars().all()}

    nvr_clients = {}
    for nvr_id, nvr in nvrs.items():
        password = decrypt_password(nvr.password_encrypted)
        nvr_clients[nvr_id] = ISAPIClient(nvr.ip_address, nvr.port, nvr.username, password)

    # 5. Process each camera
    errors = []
    cameras_restored = 0
    cameras_kept_disarmed = 0
    db_lock = asyncio.Lock()

    async def process_camera(camera: Camera):
        nonlocal cameras_restored, cameras_kept_disarmed
        client = nvr_clients[camera.nvr_id]

        try:
            # a. Update refcount
            async with db_lock:
                stmt = select(CameraDisarmRefcount).where(CameraDisarmRefcount.camera_id == camera.id)
                res = await db.execute(stmt)
                refcount = res.scalar_one_or_none()
                
                if not refcount or partition_id not in refcount.disarmed_by_partitions:
                    # Camera was not disarmed by this partition, skip
                    return

                new_partitions = list(refcount.disarmed_by_partitions)
                new_partitions.remove(partition_id)
                refcount.disarmed_by_partitions = new_partitions
                
                remaining_count = len(new_partitions)

            # b. Load and handle snapshot
            async with db_lock:
                stmt = select(CameraDetectionSnapshot).where(
                    CameraDetectionSnapshot.camera_id == camera.id,
                    CameraDetectionSnapshot.partition_id == partition_id
                )
                res = await db.execute(stmt)
                snapshot = res.scalar_one_or_none()

            if remaining_count == 0:
                # Restore detection
                if snapshot:
                    for d_type, xml in snapshot.snapshot_data.items():
                        await client.put_detection_config(camera.channel_no, d_type, xml)
                    
                    async with db_lock:
                        await db.delete(snapshot)
                
                cameras_restored += 1
            else:
                # Stay disarmed
                if snapshot:
                    async with db_lock:
                        await db.delete(snapshot)
                
                cameras_kept_disarmed += 1

        except Exception as e:
            errors.append(PartitionError(camera_id=camera.id, message=str(e)))

    await asyncio.gather(*(process_camera(c) for c in cameras))

    # 6. Update PartitionState
    state.state = "armed"
    state.last_changed_at = datetime.now(timezone.utc)
    state.last_changed_by = armed_by
    state.scheduled_rearm_at = None # ARM-05: cancel scheduled rearm
    state.error_detail = None

    # 7. Audit log
    audit = PartitionAuditLog(
        partition_id=partition_id,
        action="arm",
        performed_by=armed_by,
        audit_metadata={
            "cameras_restored": cameras_restored,
            "cameras_kept_disarmed": cameras_kept_disarmed,
            "errors_count": len(errors),
        },
    )
    db.add(audit)

    await db.commit()

    return ArmResponse(
        cameras_restored=cameras_restored,
        cameras_kept_disarmed=cameras_kept_disarmed,
        errors=errors,
    )


# ---------------------------------------------------------------------------
# CRUD service functions
# ---------------------------------------------------------------------------


async def _probe_initial_state(camera_ids: list[uuid.UUID], db: AsyncSession) -> str:
    """Query NVR detection configs to determine the real current state.

    Returns "disarmed" if ALL cameras have ALL supported detection types disabled.
    Returns "armed" in all other cases (including errors or mixed state).
    """
    if not camera_ids:
        return "armed"

    stmt = (
        select(Camera, NVRDevice)
        .join(NVRDevice, NVRDevice.id == Camera.nvr_id)
        .where(Camera.id.in_(camera_ids))
    )
    result = await db.execute(stmt)
    rows = result.all()
    if not rows:
        return "armed"

    # Build one ISAPIClient per NVR
    clients: dict[uuid.UUID, ISAPIClient] = {}
    for camera, nvr in rows:
        if nvr.id not in clients:
            clients[nvr.id] = ISAPIClient(
                nvr.ip_address, nvr.port, nvr.username, decrypt_password(nvr.password_encrypted)
            )

    # For each camera, check if any detection type is enabled
    any_enabled = False
    any_checked = False
    for camera, nvr in rows:
        client = clients[nvr.id]
        for d_type in DETECTION_TYPES:
            try:
                xml = await client.get_detection_config(camera.channel_no, d_type)
                any_checked = True
                if _is_enabled_in_xml(xml):
                    any_enabled = True
                    break
            except Exception:
                continue
        if any_enabled:
            break

    if not any_checked:
        # Could not reach NVR at all — default to armed
        return "armed"

    return "armed" if any_enabled else "disarmed"


async def create_partition(
    body: PartitionCreate,
    db: AsyncSession,
) -> PartitionRead:
    """Create a new partition with initial PartitionState and optional cameras.

    The initial state is probed from the NVR: if all cameras' detections are
    currently disabled the partition starts as 'disarmed', otherwise 'armed'.
    Falls back to 'armed' if the NVR is unreachable.
    """
    partition = Partition(
        name=body.name,
        description=body.description,
        location_id=body.location_id,
        auto_rearm_minutes=body.auto_rearm_minutes,
        alert_if_disarmed_minutes=body.alert_if_disarmed_minutes,
    )
    db.add(partition)
    await db.flush()

    # Probe the real current state from the NVR before committing
    initial_state = await _probe_initial_state(body.camera_ids or [], db)

    state = PartitionState(partition_id=partition.id, state=initial_state)
    db.add(state)

    # Add camera memberships if provided
    if body.camera_ids:
        for camera_id in body.camera_ids:
            db.add(PartitionCamera(partition_id=partition.id, camera_id=camera_id))

    await db.commit()

    return PartitionRead(
        id=partition.id,
        name=partition.name,
        description=partition.description,
        location_id=partition.location_id,
        auto_rearm_minutes=partition.auto_rearm_minutes,
        alert_if_disarmed_minutes=partition.alert_if_disarmed_minutes,
        state=state.state,
        created_at=partition.created_at,
    )


async def get_partitions(db: AsyncSession) -> List[PartitionRead]:
    """Return all non-deleted partitions with their current state."""
    stmt = (
        select(Partition, PartitionState)
        .outerjoin(PartitionState, PartitionState.partition_id == Partition.id)
        .where(Partition.deleted_at.is_(None))
        .order_by(Partition.created_at)
    )
    result = await db.execute(stmt)
    rows = result.all()

    partitions = []
    for partition, state in rows:
        partitions.append(
            PartitionRead(
                id=partition.id,
                name=partition.name,
                description=partition.description,
                location_id=partition.location_id,
                auto_rearm_minutes=partition.auto_rearm_minutes,
                alert_if_disarmed_minutes=partition.alert_if_disarmed_minutes,
                state=state.state if state else None,
                created_at=partition.created_at,
            )
        )
    return partitions


async def get_partition_detail(
    partition_id: uuid.UUID,
    db: AsyncSession,
) -> PartitionDetail:
    """Return a single non-deleted partition with its current state and member cameras (NVR info)."""
    # Load partition
    partition = await db.get(Partition, partition_id)
    if not partition or partition.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Partition not found")

    # Load state
    stmt = select(PartitionState).where(PartitionState.partition_id == partition_id)
    result = await db.execute(stmt)
    state = result.scalar_one_or_none()

    # Load cameras with NVR info via join
    stmt = (
        select(Camera, NVRDevice)
        .join(PartitionCamera, Camera.id == PartitionCamera.camera_id)
        .join(NVRDevice, Camera.nvr_id == NVRDevice.id)
        .where(PartitionCamera.partition_id == partition_id)
    )
    result = await db.execute(stmt)
    camera_rows = result.all()

    cameras = [
        CameraRead(
            id=cam.id,
            channel_no=cam.channel_no,
            name=cam.name,
            nvr_id=nvr.id,
            nvr_name=nvr.name,
            nvr_ip=nvr.ip_address,
        )
        for cam, nvr in camera_rows
    ]

    return PartitionDetail(
        id=partition.id,
        name=partition.name,
        description=partition.description,
        location_id=partition.location_id,
        auto_rearm_minutes=partition.auto_rearm_minutes,
        alert_if_disarmed_minutes=partition.alert_if_disarmed_minutes,
        state=state.state if state else None,
        created_at=partition.created_at,
        cameras=cameras,
    )


async def update_partition(
    partition_id: uuid.UUID,
    body: PartitionUpdate,
    db: AsyncSession,
) -> PartitionRead:
    """Update partition metadata fields."""
    partition = await db.get(Partition, partition_id)
    if not partition or partition.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Partition not found")

    if body.name is not None:
        partition.name = body.name
    if body.description is not None:
        partition.description = body.description
    if body.auto_rearm_minutes is not None:
        partition.auto_rearm_minutes = body.auto_rearm_minutes
    if body.alert_if_disarmed_minutes is not None:
        partition.alert_if_disarmed_minutes = body.alert_if_disarmed_minutes

    await db.flush()

    # Load current state for response
    stmt = select(PartitionState).where(PartitionState.partition_id == partition_id)
    result = await db.execute(stmt)
    state = result.scalar_one_or_none()

    await db.commit()

    return PartitionRead(
        id=partition.id,
        name=partition.name,
        description=partition.description,
        location_id=partition.location_id,
        auto_rearm_minutes=partition.auto_rearm_minutes,
        alert_if_disarmed_minutes=partition.alert_if_disarmed_minutes,
        state=state.state if state else None,
        created_at=partition.created_at,
    )


async def sync_partition_cameras(
    partition_id: uuid.UUID,
    camera_ids: List[uuid.UUID],
    db: AsyncSession,
) -> PartitionDetail:
    """Replace the entire camera membership for a partition.

    Validates that all cameras belong to the same location as the partition
    (checked via camera -> NVR -> location_id).
    """
    partition = await db.get(Partition, partition_id)
    if not partition or partition.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Partition not found")

    if camera_ids and partition.location_id is not None:
        # Validate all cameras are in the partition's location
        stmt = (
            select(Camera)
            .join(NVRDevice, Camera.nvr_id == NVRDevice.id)
            .where(Camera.id.in_(camera_ids))
        )
        result = await db.execute(stmt)
        cameras = result.scalars().all()

        found_ids = {c.id for c in cameras}
        missing = set(camera_ids) - found_ids
        if missing:
            raise HTTPException(status_code=400, detail=f"Camera(s) not found: {missing}")

        # Load NVRs for found cameras to check location
        nvr_ids = {c.nvr_id for c in cameras}
        stmt = select(NVRDevice).where(NVRDevice.id.in_(nvr_ids))
        result = await db.execute(stmt)
        nvrs = result.scalars().all()

        wrong_location = [
            str(n.id) for n in nvrs if n.location_id != partition.location_id
        ]
        if wrong_location:
            raise HTTPException(
                status_code=400,
                detail=f"Camera(s) belong to a different location than the partition",
            )

    # Delete all existing membership rows
    stmt = delete(PartitionCamera).where(PartitionCamera.partition_id == partition_id)
    await db.execute(stmt)

    # Insert new membership rows
    for camera_id in camera_ids:
        db.add(PartitionCamera(partition_id=partition_id, camera_id=camera_id))

    await db.commit()

    # Return updated detail
    return await get_partition_detail(partition_id, db)


async def delete_partition(
    partition_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    """Soft-delete a partition. Blocked if current state is 'disarmed' or 'partial'."""
    partition = await db.get(Partition, partition_id)
    if not partition or partition.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Partition not found")

    # Check current state — block deletion if disarmed or partial
    stmt = select(PartitionState).where(PartitionState.partition_id == partition_id)
    result = await db.execute(stmt)
    state = result.scalar_one_or_none()

    if state and state.state in ("disarmed", "partial"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete partition in state '{state.state}'. Arm the partition first.",
        )

    partition.deleted_at = datetime.now(timezone.utc)
    await db.commit()


async def get_partition_state(
    partition_id: uuid.UUID,
    db: AsyncSession,
) -> PartitionStateRead:
    """Return deep-dive partition state: overall state + per-camera detection status and refcounts."""
    partition = await db.get(Partition, partition_id)
    if not partition or partition.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Partition not found")

    # Load PartitionState
    stmt = select(PartitionState).where(PartitionState.partition_id == partition_id)
    result = await db.execute(stmt)
    state = result.scalar_one_or_none()

    # Load cameras with NVR info
    stmt = (
        select(Camera, NVRDevice)
        .join(PartitionCamera, Camera.id == PartitionCamera.camera_id)
        .join(NVRDevice, Camera.nvr_id == NVRDevice.id)
        .where(PartitionCamera.partition_id == partition_id)
    )
    result = await db.execute(stmt)
    camera_rows = result.all()

    camera_ids = [cam.id for cam, _ in camera_rows]

    # Bulk-load snapshots for this partition
    snapshots: Dict[uuid.UUID, Any] = {}
    if camera_ids:
        stmt = select(CameraDetectionSnapshot).where(
            CameraDetectionSnapshot.partition_id == partition_id,
            CameraDetectionSnapshot.camera_id.in_(camera_ids),
        )
        res = await db.execute(stmt)
        for snap in res.scalars().all():
            snapshots[snap.camera_id] = snap.snapshot_data

    # Bulk-load refcounts
    refcounts: Dict[uuid.UUID, List[uuid.UUID]] = {}
    if camera_ids:
        stmt = select(CameraDisarmRefcount).where(
            CameraDisarmRefcount.camera_id.in_(camera_ids)
        )
        res = await db.execute(stmt)
        for rc in res.scalars().all():
            refcounts[rc.camera_id] = rc.disarmed_by_partitions

    cameras_out = []
    for cam, nvr in camera_rows:
        disarmed_by = refcounts.get(cam.id, [])
        cameras_out.append(
            CameraStateRead(
                id=cam.id,
                channel_no=cam.channel_no,
                name=cam.name,
                nvr_id=nvr.id,
                detection_snapshot=snapshots.get(cam.id),
                disarmed_by_partitions=disarmed_by,
                disarm_count=len(disarmed_by),
            )
        )

    return PartitionStateRead(
        partition_id=partition_id,
        state=state.state if state else None,
        last_changed_at=state.last_changed_at if state else None,
        last_changed_by=state.last_changed_by if state else None,
        scheduled_rearm_at=state.scheduled_rearm_at if state else None,
        error_detail=state.error_detail if state else None,
        cameras=cameras_out,
    )


async def get_dashboard(db: AsyncSession) -> DashboardResponse:
    """Return an aggregated dashboard view of all non-deleted partitions.

    - Calculates disarmed_minutes at request time for partitions in state 'disarmed' or 'partial'.
    - Sets overdue=True when alert_if_disarmed_minutes is configured and exceeded.
    - Sorts active partitions (error / partial / disarmed) before armed ones.
    """
    stmt = (
        select(Partition, PartitionState)
        .outerjoin(PartitionState, PartitionState.partition_id == Partition.id)
        .where(Partition.deleted_at.is_(None))
        .order_by(Partition.created_at)
    )
    result = await db.execute(stmt)
    rows = result.all()

    _ACTIVE_STATES = {"error", "partial", "disarmed"}

    now = datetime.now(timezone.utc)
    entries: list[DashboardPartitionEntry] = []

    for partition, state in rows:
        current_state = state.state if state else None

        disarmed_minutes: Optional[float] = None
        overdue: bool = False

        if current_state in ("disarmed", "partial") and state and state.last_changed_at:
            elapsed = now - state.last_changed_at
            disarmed_minutes = elapsed.total_seconds() / 60.0

            if partition.alert_if_disarmed_minutes is not None:
                overdue = disarmed_minutes >= partition.alert_if_disarmed_minutes

        entries.append(
            DashboardPartitionEntry(
                id=partition.id,
                name=partition.name,
                description=partition.description,
                location_id=partition.location_id,
                state=current_state,
                disarmed_minutes=disarmed_minutes,
                overdue=overdue,
                scheduled_rearm_at=state.scheduled_rearm_at if state else None,
                last_changed_at=state.last_changed_at if state else None,
                last_changed_by=state.last_changed_by if state else None,
            )
        )

    # Sort: active (error/partial/disarmed) first, then armed / unknown
    entries.sort(key=lambda e: (0 if e.state in _ACTIVE_STATES else 1, e.name))

    active_count = sum(1 for e in entries if e.state in _ACTIVE_STATES)

    return DashboardResponse(
        partitions=entries,
        total=len(entries),
        active_count=active_count,
    )


async def get_partition_audit_log(
    partition_id: uuid.UUID,
    limit: int,
    offset: int,
    db: AsyncSession,
) -> PaginatedAuditLog:
    """Return paginated audit log for a partition."""
    partition = await db.get(Partition, partition_id)
    if not partition or partition.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Partition not found")

    from sqlalchemy import func as sql_func

    # Total count
    count_stmt = select(sql_func.count(PartitionAuditLog.id)).where(
        PartitionAuditLog.partition_id == partition_id
    )
    total = (await db.execute(count_stmt)).scalar_one()

    # Paginated rows — newest first
    stmt = (
        select(PartitionAuditLog)
        .where(PartitionAuditLog.partition_id == partition_id)
        .order_by(PartitionAuditLog.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()

    items = [
        AuditLogEntryRead(
            id=row.id,
            partition_id=row.partition_id,
            action=row.action,
            performed_by=row.performed_by,
            audit_metadata=row.audit_metadata,
            created_at=row.created_at,
        )
        for row in rows
    ]

    return PaginatedAuditLog(total=total, limit=limit, offset=offset, items=items)
