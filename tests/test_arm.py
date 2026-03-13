import pytest
import uuid
from datetime import datetime, timezone
from sqlalchemy import select
from app.locations.models import Location
from app.nvrs.models import NVRDevice
from app.cameras.models import Camera
from app.partitions.models import (
    Partition,
    PartitionCamera,
    PartitionState,
    CameraDetectionSnapshot,
    CameraDisarmRefcount,
    PartitionAuditLog,
)
from app.core.crypto import encrypt_password
from tests.mocks import MockISAPIClient

@pytest.fixture
def mock_isapi(monkeypatch):
    monkeypatch.setattr("app.partitions.service.ISAPIClient", MockISAPIClient)

@pytest.mark.asyncio
async def test_arm_success_single_partition(client, db_session, mock_isapi):
    # Setup: 1 Location, 1 NVR, 1 Camera, 1 Partition, 1 snapshot, 1 refcount
    loc = Location(name="L", timezone="UTC")
    db_session.add(loc)
    await db_session.flush()
    nvr = NVRDevice(location_id=loc.id, name="N", ip_address="1.2.3.4", username="u", password_encrypted=encrypt_password("p"))
    db_session.add(nvr)
    await db_session.flush()
    cam = Camera(nvr_id=nvr.id, channel_no=1)
    db_session.add(cam)
    await db_session.flush()
    part = Partition(name="P")
    db_session.add(part)
    await db_session.flush()
    db_session.add(PartitionCamera(partition_id=part.id, camera_id=cam.id))
    
    db_session.add(PartitionState(partition_id=part.id, state="disarmed", scheduled_rearm_at=datetime.now(timezone.utc)))
    db_session.add(CameraDetectionSnapshot(camera_id=cam.id, partition_id=part.id, snapshot_data={"MotionDetection": "<xml/>"}))
    db_session.add(CameraDisarmRefcount(camera_id=cam.id, disarmed_by_partitions=[part.id]))
    await db_session.commit()

    # Act
    resp = await client.post(f"/api/partitions/{part.id}/arm", json={"armed_by": "test-user"})

    # Assert
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["cameras_restored"] == 1
    assert data["data"]["cameras_kept_disarmed"] == 0

    # Verify state
    stmt = select(PartitionState).where(PartitionState.partition_id == part.id)
    res = await db_session.execute(stmt)
    state = res.scalar_one()
    assert state.state == "armed"
    assert state.scheduled_rearm_at is None

    # Verify snapshot deleted
    stmt = select(CameraDetectionSnapshot).where(CameraDetectionSnapshot.camera_id == cam.id)
    res = await db_session.execute(stmt)
    assert res.scalar_one_or_none() is None

    # Verify refcount empty
    stmt = select(CameraDisarmRefcount).where(CameraDisarmRefcount.camera_id == cam.id)
    res = await db_session.execute(stmt)
    refcount = res.scalar_one()
    assert len(refcount.disarmed_by_partitions) == 0

@pytest.mark.asyncio
async def test_arm_multi_partition_stay_disarmed(client, db_session, mock_isapi):
    # Setup: 1 Camera, 2 Partitions, both disarmed it
    loc = Location(name="L", timezone="UTC")
    db_session.add(loc)
    await db_session.flush()
    nvr = NVRDevice(location_id=loc.id, name="N", ip_address="1.2.3.4", username="u", password_encrypted=encrypt_password("p"))
    db_session.add(nvr)
    await db_session.flush()
    cam = Camera(nvr_id=nvr.id, channel_no=1)
    db_session.add(cam)
    await db_session.flush()
    
    part1 = Partition(name="P1")
    part2 = Partition(name="P2")
    db_session.add_all([part1, part2])
    await db_session.flush()
    
    db_session.add(PartitionCamera(partition_id=part1.id, camera_id=cam.id))
    db_session.add(PartitionCamera(partition_id=part2.id, camera_id=cam.id))
    
    db_session.add(PartitionState(partition_id=part1.id, state="disarmed"))
    db_session.add(PartitionState(partition_id=part2.id, state="disarmed"))
    
    # Both have snapshots
    db_session.add(CameraDetectionSnapshot(camera_id=cam.id, partition_id=part1.id, snapshot_data={"MD": "xml"}))
    db_session.add(CameraDetectionSnapshot(camera_id=cam.id, partition_id=part2.id, snapshot_data={"MD": "xml"}))
    
    db_session.add(CameraDisarmRefcount(camera_id=cam.id, disarmed_by_partitions=[part1.id, part2.id]))
    await db_session.commit()

    # Act: Arm Part1
    resp = await client.post(f"/api/partitions/{part1.id}/arm", json={"armed_by": "test"})

    # Assert
    data = resp.json()
    assert data["data"]["cameras_restored"] == 0
    assert data["data"]["cameras_kept_disarmed"] == 1

    # Verify snapshot for part1 is deleted, but part2 remains
    stmt = select(CameraDetectionSnapshot).where(CameraDetectionSnapshot.camera_id == cam.id)
    res = await db_session.execute(stmt)
    snapshots = res.scalars().all()
    assert len(snapshots) == 1
    assert snapshots[0].partition_id == part2.id

    # Verify refcount is 1
    stmt = select(CameraDisarmRefcount).where(CameraDisarmRefcount.camera_id == cam.id)
    res = await db_session.execute(stmt)
    refcount = res.scalar_one()
    assert refcount.disarmed_by_partitions == [part2.id]

@pytest.mark.asyncio
async def test_arm_idempotent(client, db_session, mock_isapi):
    part = Partition(name="P")
    db_session.add(part)
    await db_session.flush()
    db_session.add(PartitionState(partition_id=part.id, state="armed"))
    await db_session.commit()

    resp = await client.post(f"/api/partitions/{part.id}/arm", json={"armed_by": "test"})
    assert resp.status_code == 200
    assert resp.json()["data"]["cameras_restored"] == 0

@pytest.mark.asyncio
async def test_arm_from_partial_state_succeeds(client, db_session, mock_isapi):
    """ARM-05: Arm proceeds normally when partition state is 'partial'."""
    loc = Location(name="L", timezone="UTC")
    db_session.add(loc)
    await db_session.flush()
    nvr = NVRDevice(
        location_id=loc.id, name="N", ip_address="1.2.3.4",
        username="u", password_encrypted=encrypt_password("p")
    )
    db_session.add(nvr)
    await db_session.flush()
    cam = Camera(nvr_id=nvr.id, channel_no=1)
    db_session.add(cam)
    await db_session.flush()
    part = Partition(name="P")
    db_session.add(part)
    await db_session.flush()
    db_session.add(PartitionCamera(partition_id=part.id, camera_id=cam.id))
    # State is "partial" — arm should still proceed
    db_session.add(PartitionState(partition_id=part.id, state="partial"))
    db_session.add(CameraDetectionSnapshot(
        camera_id=cam.id, partition_id=part.id, snapshot_data={"MotionDetection": "<xml/>"}
    ))
    db_session.add(CameraDisarmRefcount(camera_id=cam.id, disarmed_by_partitions=[part.id]))
    await db_session.commit()

    resp = await client.post(f"/api/partitions/{part.id}/arm", json={"armed_by": "test-user"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["cameras_restored"] == 1
    assert data["data"]["cameras_kept_disarmed"] == 0

    stmt = select(PartitionState).where(PartitionState.partition_id == part.id)
    res = await db_session.execute(stmt)
    state = res.scalar_one()
    assert state.state == "armed"


@pytest.mark.asyncio
async def test_arm_from_error_state_succeeds(client, db_session, mock_isapi):
    """ARM-05: Arm proceeds normally when partition state is 'error'."""
    loc = Location(name="L", timezone="UTC")
    db_session.add(loc)
    await db_session.flush()
    nvr = NVRDevice(
        location_id=loc.id, name="N", ip_address="1.2.3.4",
        username="u", password_encrypted=encrypt_password("p")
    )
    db_session.add(nvr)
    await db_session.flush()
    cam = Camera(nvr_id=nvr.id, channel_no=1)
    db_session.add(cam)
    await db_session.flush()
    part = Partition(name="P")
    db_session.add(part)
    await db_session.flush()
    db_session.add(PartitionCamera(partition_id=part.id, camera_id=cam.id))
    # State is "error" — arm should still proceed
    db_session.add(PartitionState(
        partition_id=part.id, state="error", error_detail="prior NVR failure"
    ))
    db_session.add(CameraDetectionSnapshot(
        camera_id=cam.id, partition_id=part.id, snapshot_data={"MotionDetection": "<xml/>"}
    ))
    db_session.add(CameraDisarmRefcount(camera_id=cam.id, disarmed_by_partitions=[part.id]))
    await db_session.commit()

    resp = await client.post(f"/api/partitions/{part.id}/arm", json={"armed_by": "test-user"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["cameras_restored"] == 1
    assert data["data"]["cameras_kept_disarmed"] == 0

    stmt = select(PartitionState).where(PartitionState.partition_id == part.id)
    res = await db_session.execute(stmt)
    state = res.scalar_one()
    assert state.state == "armed"


@pytest.mark.asyncio
async def test_arm_creates_audit_log_entry(client, db_session, mock_isapi):
    """ARM-06: Arm creates a PartitionAuditLog entry with action='arm' and correct performed_by."""
    loc = Location(name="L", timezone="UTC")
    db_session.add(loc)
    await db_session.flush()
    nvr = NVRDevice(
        location_id=loc.id, name="N", ip_address="1.2.3.4",
        username="u", password_encrypted=encrypt_password("p")
    )
    db_session.add(nvr)
    await db_session.flush()
    cam = Camera(nvr_id=nvr.id, channel_no=1)
    db_session.add(cam)
    await db_session.flush()
    part = Partition(name="P")
    db_session.add(part)
    await db_session.flush()
    db_session.add(PartitionCamera(partition_id=part.id, camera_id=cam.id))
    db_session.add(PartitionState(partition_id=part.id, state="disarmed"))
    db_session.add(CameraDetectionSnapshot(
        camera_id=cam.id, partition_id=part.id, snapshot_data={"MotionDetection": "<xml/>"}
    ))
    db_session.add(CameraDisarmRefcount(camera_id=cam.id, disarmed_by_partitions=[part.id]))
    await db_session.commit()

    resp = await client.post(f"/api/partitions/{part.id}/arm", json={"armed_by": "test-user"})

    assert resp.status_code == 200
    assert resp.json()["success"] is True

    stmt = select(PartitionAuditLog).where(
        PartitionAuditLog.partition_id == part.id,
        PartitionAuditLog.action == "arm",
    )
    res = await db_session.execute(stmt)
    audit = res.scalar_one_or_none()
    assert audit is not None
    assert audit.performed_by == "test-user"


@pytest.mark.asyncio
async def test_arm_calls_cancel_rearm(client, db_session, mock_isapi, mock_scheduler_calls):
    """JOB-01: arm_partition must call cancel_rearm unconditionally to remove any pending auto-rearm job."""
    loc = Location(name="L", timezone="UTC")
    db_session.add(loc)
    await db_session.flush()
    nvr = NVRDevice(
        location_id=loc.id, name="N", ip_address="1.2.3.4",
        username="u", password_encrypted=encrypt_password("p")
    )
    db_session.add(nvr)
    await db_session.flush()
    cam = Camera(nvr_id=nvr.id, channel_no=1)
    db_session.add(cam)
    await db_session.flush()
    part = Partition(name="P")
    db_session.add(part)
    await db_session.flush()
    db_session.add(PartitionCamera(partition_id=part.id, camera_id=cam.id))
    db_session.add(PartitionState(
        partition_id=part.id,
        state="disarmed",
        scheduled_rearm_at=datetime.now(timezone.utc),
    ))
    db_session.add(CameraDetectionSnapshot(
        camera_id=cam.id, partition_id=part.id, snapshot_data={"MotionDetection": "<xml/>"}
    ))
    db_session.add(CameraDisarmRefcount(camera_id=cam.id, disarmed_by_partitions=[part.id]))
    await db_session.commit()

    resp = await client.post(f"/api/partitions/{part.id}/arm", json={"armed_by": "test-user"})

    assert resp.status_code == 200
    assert resp.json()["success"] is True

    # JOB-01: cancel_rearm must have been called with the partition_id
    mock_cancel = mock_scheduler_calls["cancel_rearm"]
    mock_cancel.assert_called_once()
    call_args = mock_cancel.call_args
    assert call_args.args[0] == part.id


@pytest.mark.asyncio
async def test_arm_restore_failure(client, db_session, monkeypatch):
    class FailingPutMock(MockISAPIClient):
        async def put_detection_config(self, *args, **kwargs):
            raise Exception("ISAPI PUT Failed")
    
    monkeypatch.setattr("app.partitions.service.ISAPIClient", FailingPutMock)

    loc = Location(name="L", timezone="UTC")
    db_session.add(loc)
    await db_session.flush()
    nvr = NVRDevice(location_id=loc.id, name="N", ip_address="1", username="u", password_encrypted=encrypt_password("p"))
    db_session.add(nvr)
    await db_session.flush()
    cam = Camera(nvr_id=nvr.id, channel_no=1)
    db_session.add(cam)
    await db_session.flush()
    part = Partition(name="P")
    db_session.add(part)
    await db_session.flush()
    db_session.add(PartitionCamera(partition_id=part.id, camera_id=cam.id))
    db_session.add(PartitionState(partition_id=part.id, state="disarmed"))
    db_session.add(CameraDetectionSnapshot(camera_id=cam.id, partition_id=part.id, snapshot_data={"MD": "xml"}))
    db_session.add(CameraDisarmRefcount(camera_id=cam.id, disarmed_by_partitions=[part.id]))
    await db_session.commit()

    # Act
    resp = await client.post(f"/api/partitions/{part.id}/arm", json={"armed_by": "test"})

    # Assert
    data = resp.json()
    assert data["success"] is True # Arm succeeds but with errors
    assert data["data"]["cameras_restored"] == 0
    assert len(data["data"]["errors"]) == 1
    assert "ISAPI PUT Failed" in data["data"]["errors"][0]["message"]

    # Snapshot should NOT be deleted on failure
    stmt = select(CameraDetectionSnapshot).where(CameraDetectionSnapshot.camera_id == cam.id)
    res = await db_session.execute(stmt)
    assert res.scalar_one_or_none() is not None
