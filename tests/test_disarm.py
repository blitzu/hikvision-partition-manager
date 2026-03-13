import pytest
import uuid
from datetime import datetime, timezone, timedelta
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
async def test_disarm_success(client, db_session, mock_isapi):
    # Setup: Location -> NVR -> Camera -> Partition -> PartitionCamera
    loc = Location(name="Test Location", timezone="UTC")
    db_session.add(loc)
    await db_session.flush()

    nvr = NVRDevice(
        location_id=loc.id,
        name="Test NVR",
        ip_address="1.2.3.4",
        port=80,
        username="admin",
        password_encrypted=encrypt_password("password"),
        status="unknown",
    )
    db_session.add(nvr)
    await db_session.flush()

    cam = Camera(nvr_id=nvr.id, channel_no=1, name="Cam 1")
    db_session.add(cam)
    await db_session.flush()

    part = Partition(name="Test Partition", auto_rearm_minutes=60)
    db_session.add(part)
    await db_session.flush()

    pc = PartitionCamera(partition_id=part.id, camera_id=cam.id)
    db_session.add(pc)
    await db_session.commit()

    # Act
    resp = await client.post(
        f"/api/partitions/{part.id}/disarm",
        json={"disarmed_by": "test-user", "reason": "testing"},
    )

    # Assert
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["cameras_disarmed"] == 1
    assert data["data"]["cameras_kept_disarmed_by_other_partition"] == 0
    assert data["data"]["scheduled_rearm_at"] is not None

    # Verify Database State
    # 1. PartitionState
    stmt = select(PartitionState).where(PartitionState.partition_id == part.id)
    res = await db_session.execute(stmt)
    state = res.scalar_one()
    assert state.state == "disarmed"
    assert state.last_changed_by == "test-user"

    # 2. CameraDetectionSnapshot
    stmt = select(CameraDetectionSnapshot).where(CameraDetectionSnapshot.camera_id == cam.id)
    res = await db_session.execute(stmt)
    snapshot = res.scalar_one()
    assert "MotionDetection" in snapshot.snapshot_data

    # 3. CameraDisarmRefcount
    stmt = select(CameraDisarmRefcount).where(CameraDisarmRefcount.camera_id == cam.id)
    res = await db_session.execute(stmt)
    refcount = res.scalar_one()
    assert part.id in refcount.disarmed_by_partitions

    # 4. Audit Log
    stmt = select(PartitionAuditLog).where(PartitionAuditLog.partition_id == part.id)
    res = await db_session.execute(stmt)
    audits = res.scalars().all()
    assert len(audits) == 1
    assert audits[0].action == "disarm"
    assert audits[0].performed_by == "test-user"

@pytest.mark.asyncio
async def test_disarm_idempotent(client, db_session, mock_isapi):
    # Setup
    loc = Location(name="Test Location", timezone="UTC")
    db_session.add(loc)
    await db_session.flush()
    nvr = NVRDevice(location_id=loc.id, name="NVR", ip_address="1.1.1.1", username="a", password_encrypted=encrypt_password("p"), status="unknown")
    db_session.add(nvr)
    await db_session.flush()
    cam = Camera(nvr_id=nvr.id, channel_no=1)
    db_session.add(cam)
    await db_session.flush()
    part = Partition(name="P")
    db_session.add(part)
    await db_session.flush()
    db_session.add(PartitionCamera(partition_id=part.id, camera_id=cam.id))
    
    # Pre-set state to disarmed
    db_session.add(PartitionState(partition_id=part.id, state="disarmed"))
    await db_session.commit()

    # Act
    resp = await client.post(f"/api/partitions/{part.id}/disarm", json={"disarmed_by": "test-user"})

    # Assert
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["cameras_disarmed"] == 0 # Idempotent no-op

@pytest.mark.asyncio
async def test_disarm_snapshot_protection(client, db_session, mock_isapi):
    # Setup: camera already has snapshot
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
    
    original_xml = "<OriginalSnapshot/>"
    db_session.add(CameraDetectionSnapshot(
        camera_id=cam.id,
        partition_id=part.id,
        snapshot_data={"MotionDetection": original_xml}
    ))
    await db_session.commit()

    # Act
    resp = await client.post(f"/api/partitions/{part.id}/disarm", json={"disarmed_by": "test"})

    # Assert
    # Snapshot should not be overwritten
    stmt = select(CameraDetectionSnapshot).where(CameraDetectionSnapshot.camera_id == cam.id)
    res = await db_session.execute(stmt)
    snapshot = res.scalar_one()
    assert snapshot.snapshot_data["MotionDetection"] == original_xml

@pytest.mark.asyncio
async def test_disarm_nvr_failure(client, db_session, monkeypatch):
    class FailingMockISAPIClient(MockISAPIClient):
        async def get_device_info(self) -> dict:
            raise Exception("Connection Refused")

    monkeypatch.setattr("app.partitions.service.ISAPIClient", FailingMockISAPIClient)

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
    await db_session.commit()

    # Act
    resp = await client.post(f"/api/partitions/{part.id}/disarm", json={"disarmed_by": "test"})

    # Assert
    assert resp.status_code == 200 # Wrapped in APIResponse
    data = resp.json()
    assert data["success"] is False
    assert "Connection Refused" in data["error"]

    # Verify state=error in DB
    stmt = select(PartitionState).where(PartitionState.partition_id == part.id)
    res = await db_session.execute(stmt)
    state = res.scalar_one()
    assert state.state == "error"
    assert "Connection Refused" in state.error_detail

@pytest.mark.asyncio
async def test_disarm_camera_already_disarmed_by_other_partition(client, db_session, mock_isapi):
    """DARM-09: When another partition has already disarmed a camera, cameras_kept_disarmed_by_other_partition is incremented.

    The camera's refcount array already contains another partition's ID, so after this
    partition appends its ID the length becomes > 1, triggering the counter.
    """
    loc = Location(name="L", timezone="UTC")
    db_session.add(loc)
    await db_session.flush()

    nvr = NVRDevice(
        location_id=loc.id,
        name="N",
        ip_address="1.2.3.4",
        username="u",
        password_encrypted=encrypt_password("p"),
        status="unknown",
    )
    db_session.add(nvr)
    await db_session.flush()

    cam = Camera(nvr_id=nvr.id, channel_no=1)
    db_session.add(cam)
    await db_session.flush()

    # Partition A (another partition) already disarmed this camera
    other_part = Partition(name="Other Partition")
    db_session.add(other_part)
    await db_session.flush()

    # The partition under test
    this_part = Partition(name="This Partition")
    db_session.add(this_part)
    await db_session.flush()

    db_session.add(PartitionCamera(partition_id=this_part.id, camera_id=cam.id))

    # Pre-existing refcount from the other partition
    db_session.add(CameraDisarmRefcount(camera_id=cam.id, disarmed_by_partitions=[other_part.id]))

    # Pre-existing snapshot from the other partition (DARM-04: won't be overwritten)
    original_xml = "<MotionDetection><enabled>true</enabled></MotionDetection>"
    db_session.add(CameraDetectionSnapshot(
        camera_id=cam.id,
        partition_id=other_part.id,
        snapshot_data={"MotionDetection": original_xml},
    ))

    await db_session.commit()

    # Act: disarm this_part
    resp = await client.post(
        f"/api/partitions/{this_part.id}/disarm",
        json={"disarmed_by": "test-user"},
    )

    # Assert
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    # The camera was already disarmed by another partition — counter incremented
    assert data["data"]["cameras_kept_disarmed_by_other_partition"] == 1
    # The camera IS still disarmed by this partition (refcount updated)
    assert data["data"]["cameras_disarmed"] == 0

    # Verify refcount now has both partitions
    stmt = select(CameraDisarmRefcount).where(CameraDisarmRefcount.camera_id == cam.id)
    res = await db_session.execute(stmt)
    refcount = res.scalar_one()
    assert other_part.id in refcount.disarmed_by_partitions
    assert this_part.id in refcount.disarmed_by_partitions


@pytest.mark.asyncio
async def test_disarm_partial_failure(client, db_session, monkeypatch):
    # Mock where first camera succeeds, second fails
    class PartialMockISAPIClient:
        def __init__(self, *args, **kwargs):
            pass
        async def get_device_info(self) -> dict:
            return {}
        async def get_detection_config(self, channel_no: int, detection_type: str) -> str:
            if channel_no == 2:
                raise Exception("Camera 2 Failed")
            return "<enabled>true</enabled>"
        async def put_detection_config(self, channel_no: int, detection_type: str, xml: str) -> None:
            if channel_no == 2:
                raise Exception("Camera 2 Failed")

    monkeypatch.setattr("app.partitions.service.ISAPIClient", PartialMockISAPIClient)

    loc = Location(name="L", timezone="UTC")
    db_session.add(loc)
    await db_session.flush()
    nvr = NVRDevice(location_id=loc.id, name="N", ip_address="1", username="u", password_encrypted=encrypt_password("p"))
    db_session.add(nvr)
    await db_session.flush()
    
    cam1 = Camera(nvr_id=nvr.id, channel_no=1)
    cam2 = Camera(nvr_id=nvr.id, channel_no=2)
    db_session.add_all([cam1, cam2])
    await db_session.flush()
    
    part = Partition(name="P")
    db_session.add(part)
    await db_session.flush()
    db_session.add(PartitionCamera(partition_id=part.id, camera_id=cam1.id))
    db_session.add(PartitionCamera(partition_id=part.id, camera_id=cam2.id))
    await db_session.commit()

    # Act
    resp = await client.post(f"/api/partitions/{part.id}/disarm", json={"disarmed_by": "test"})

    # Assert
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["cameras_disarmed"] == 1
    assert len(data["data"]["errors"]) == 1
    assert "Could not retrieve any detection configuration" in data["data"]["errors"][0]["message"]
    # Verify state=partial
    stmt = select(PartitionState).where(PartitionState.partition_id == part.id)
    res = await db_session.execute(stmt)
    state = res.scalar_one()
    assert state.state == "partial"
