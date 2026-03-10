"""Unit tests for Partition CRUD API.

Covers:
- POST /api/partitions — create partition (with and without cameras)
- GET /api/partitions — list non-deleted partitions
- GET /api/partitions/{id} — detail with cameras and NVR info
- PATCH /api/partitions/{id} — metadata update
- DELETE /api/partitions/{id} — soft-delete and deletion guard
- PUT /api/partitions/{id}/cameras — replace camera membership, location validation
"""
import pytest
import uuid
from sqlalchemy import select

from app.locations.models import Location
from app.nvrs.models import NVRDevice
from app.cameras.models import Camera
from app.partitions.models import (
    Partition,
    PartitionCamera,
    PartitionState,
)
from app.core.crypto import encrypt_password


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _make_location(db, name="Test Location"):
    loc = Location(name=name, timezone="UTC")
    db.add(loc)
    await db.flush()
    return loc


async def _make_nvr(db, location_id, ip="1.2.3.4"):
    nvr = NVRDevice(
        location_id=location_id,
        name="Test NVR",
        ip_address=ip,
        port=80,
        username="admin",
        password_encrypted=encrypt_password("password"),
        status="unknown",
    )
    db.add(nvr)
    await db.flush()
    return nvr


async def _make_camera(db, nvr_id, channel_no=1):
    cam = Camera(nvr_id=nvr_id, channel_no=channel_no, name=f"Cam {channel_no}")
    db.add(cam)
    await db.flush()
    return cam


async def _make_partition(db, name="Test Partition", location_id=None, state="armed"):
    part = Partition(name=name, location_id=location_id)
    db.add(part)
    await db.flush()
    ps = PartitionState(partition_id=part.id, state=state)
    db.add(ps)
    await db.flush()
    return part


# ---------------------------------------------------------------------------
# POST /api/partitions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_partition_minimal(client, db_session):
    """Create a partition with only a name."""
    resp = await client.post(
        "/api/partitions",
        json={"name": "Zone A"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    part = data["data"]
    assert part["name"] == "Zone A"
    assert part["state"] == "armed"
    assert part["id"] is not None


@pytest.mark.asyncio
async def test_create_partition_with_cameras(client, db_session):
    """Create a partition with cameras pre-assigned."""
    loc = await _make_location(db_session)
    nvr = await _make_nvr(db_session, loc.id)
    cam = await _make_camera(db_session, nvr.id)
    await db_session.commit()

    resp = await client.post(
        "/api/partitions",
        json={
            "name": "Zone B",
            "location_id": str(loc.id),
            "camera_ids": [str(cam.id)],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["name"] == "Zone B"

    # Verify camera membership in DB
    stmt = select(PartitionCamera).where(
        PartitionCamera.partition_id == uuid.UUID(data["data"]["id"])
    )
    result = await db_session.execute(stmt)
    pcs = result.scalars().all()
    assert len(pcs) == 1
    assert pcs[0].camera_id == cam.id


@pytest.mark.asyncio
async def test_create_partition_creates_partition_state(client, db_session):
    """Creating a partition also creates an armed PartitionState."""
    resp = await client.post("/api/partitions", json={"name": "Zone C"})
    assert resp.status_code == 200
    partition_id = uuid.UUID(resp.json()["data"]["id"])

    stmt = select(PartitionState).where(PartitionState.partition_id == partition_id)
    result = await db_session.execute(stmt)
    state = result.scalar_one()
    assert state.state == "armed"


# ---------------------------------------------------------------------------
# GET /api/partitions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_partitions(client, db_session):
    """List returns only non-deleted partitions."""
    await _make_partition(db_session, name="Active One")
    deleted = await _make_partition(db_session, name="Deleted One")
    from datetime import datetime, timezone
    deleted.deleted_at = datetime.now(timezone.utc)
    await db_session.commit()

    resp = await client.get("/api/partitions")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    names = [p["name"] for p in data["data"]]
    assert "Active One" in names
    assert "Deleted One" not in names


@pytest.mark.asyncio
async def test_list_partitions_empty(client, db_session):
    """List returns empty list when no partitions exist."""
    resp = await client.get("/api/partitions")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["data"] == []


# ---------------------------------------------------------------------------
# GET /api/partitions/{id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_partition_detail_with_cameras(client, db_session):
    """Detail endpoint returns partition with cameras and NVR info."""
    loc = await _make_location(db_session)
    nvr = await _make_nvr(db_session, loc.id)
    cam = await _make_camera(db_session, nvr.id, channel_no=3)
    part = await _make_partition(db_session, location_id=loc.id)
    db_session.add(PartitionCamera(partition_id=part.id, camera_id=cam.id))
    await db_session.commit()

    resp = await client.get(f"/api/partitions/{part.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    detail = data["data"]
    assert detail["id"] == str(part.id)
    assert len(detail["cameras"]) == 1
    cam_data = detail["cameras"][0]
    assert cam_data["channel_no"] == 3
    assert cam_data["nvr_id"] == str(nvr.id)
    assert cam_data["nvr_name"] == "Test NVR"
    assert cam_data["nvr_ip"] == "1.2.3.4"


@pytest.mark.asyncio
async def test_get_partition_detail_not_found(client, db_session):
    """Detail endpoint returns error for non-existent partition."""
    fake_id = uuid.uuid4()
    resp = await client.get(f"/api/partitions/{fake_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert "not found" in data["error"].lower()


@pytest.mark.asyncio
async def test_get_deleted_partition_not_found(client, db_session):
    """Detail endpoint returns 404 for soft-deleted partitions."""
    from datetime import datetime, timezone
    part = await _make_partition(db_session)
    part.deleted_at = datetime.now(timezone.utc)
    await db_session.commit()

    resp = await client.get(f"/api/partitions/{part.id}")
    data = resp.json()
    assert data["success"] is False


# ---------------------------------------------------------------------------
# PATCH /api/partitions/{id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_partition(client, db_session):
    """Update name and description."""
    part = await _make_partition(db_session, name="Old Name")
    await db_session.commit()

    resp = await client.patch(
        f"/api/partitions/{part.id}",
        json={"name": "New Name", "auto_rearm_minutes": 30},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["name"] == "New Name"
    assert data["data"]["auto_rearm_minutes"] == 30


@pytest.mark.asyncio
async def test_update_partition_not_found(client, db_session):
    """PATCH on non-existent partition returns error."""
    fake_id = uuid.uuid4()
    resp = await client.patch(f"/api/partitions/{fake_id}", json={"name": "x"})
    data = resp.json()
    assert data["success"] is False


# ---------------------------------------------------------------------------
# DELETE /api/partitions/{id} — soft-delete and deletion guard
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_partition_soft_delete(client, db_session):
    """DELETE sets deleted_at and hides partition from list."""
    part = await _make_partition(db_session, name="To Delete", state="armed")
    await db_session.commit()

    resp = await client.delete(f"/api/partitions/{part.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True

    # Should no longer appear in list
    list_resp = await client.get("/api/partitions")
    names = [p["name"] for p in list_resp.json()["data"]]
    assert "To Delete" not in names

    # DB should have deleted_at set
    await db_session.refresh(part)
    assert part.deleted_at is not None


@pytest.mark.asyncio
async def test_delete_partition_blocked_if_disarmed(client, db_session):
    """DELETE returns 400 if partition state is 'disarmed'."""
    part = await _make_partition(db_session, name="Disarmed Part", state="disarmed")
    await db_session.commit()

    resp = await client.delete(f"/api/partitions/{part.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert "disarmed" in data["error"].lower()


@pytest.mark.asyncio
async def test_delete_partition_blocked_if_partial(client, db_session):
    """DELETE returns error if partition state is 'partial'."""
    part = await _make_partition(db_session, name="Partial Part", state="partial")
    await db_session.commit()

    resp = await client.delete(f"/api/partitions/{part.id}")
    data = resp.json()
    assert data["success"] is False
    assert "partial" in data["error"].lower()


@pytest.mark.asyncio
async def test_delete_partition_not_found(client, db_session):
    """DELETE on non-existent partition returns error."""
    fake_id = uuid.uuid4()
    resp = await client.delete(f"/api/partitions/{fake_id}")
    data = resp.json()
    assert data["success"] is False


# ---------------------------------------------------------------------------
# PUT /api/partitions/{id}/cameras — camera sync
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sync_cameras_replaces_membership(client, db_session):
    """PUT /cameras replaces the entire camera membership."""
    loc = await _make_location(db_session)
    nvr = await _make_nvr(db_session, loc.id)
    cam1 = await _make_camera(db_session, nvr.id, channel_no=1)
    cam2 = await _make_camera(db_session, nvr.id, channel_no=2)
    part = await _make_partition(db_session, location_id=loc.id)
    # Start with cam1
    db_session.add(PartitionCamera(partition_id=part.id, camera_id=cam1.id))
    await db_session.commit()

    # Sync to cam2 only
    resp = await client.put(
        f"/api/partitions/{part.id}/cameras",
        json={"camera_ids": [str(cam2.id)]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    cam_ids = [c["id"] for c in data["data"]["cameras"]]
    assert str(cam2.id) in cam_ids
    assert str(cam1.id) not in cam_ids


@pytest.mark.asyncio
async def test_sync_cameras_empty_replaces_all(client, db_session):
    """PUT /cameras with empty list removes all camera memberships."""
    loc = await _make_location(db_session)
    nvr = await _make_nvr(db_session, loc.id)
    cam = await _make_camera(db_session, nvr.id)
    part = await _make_partition(db_session, location_id=loc.id)
    db_session.add(PartitionCamera(partition_id=part.id, camera_id=cam.id))
    await db_session.commit()

    resp = await client.put(
        f"/api/partitions/{part.id}/cameras",
        json={"camera_ids": []},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["cameras"] == []


@pytest.mark.asyncio
async def test_sync_cameras_location_validation(client, db_session):
    """PUT /cameras rejects cameras from a different location."""
    loc1 = await _make_location(db_session, name="Location 1")
    loc2 = await _make_location(db_session, name="Location 2")
    nvr1 = await _make_nvr(db_session, loc1.id, ip="1.1.1.1")
    nvr2 = await _make_nvr(db_session, loc2.id, ip="2.2.2.2")
    cam1 = await _make_camera(db_session, nvr1.id, channel_no=1)
    cam2 = await _make_camera(db_session, nvr2.id, channel_no=1)
    # Partition belongs to loc1
    part = await _make_partition(db_session, location_id=loc1.id)
    await db_session.commit()

    # Try to add cam2 (belongs to loc2)
    resp = await client.put(
        f"/api/partitions/{part.id}/cameras",
        json={"camera_ids": [str(cam2.id)]},
    )
    data = resp.json()
    assert data["success"] is False
    assert "location" in data["error"].lower()


@pytest.mark.asyncio
async def test_sync_cameras_partition_not_found(client, db_session):
    """PUT /cameras on non-existent partition returns error."""
    fake_id = uuid.uuid4()
    resp = await client.put(
        f"/api/partitions/{fake_id}/cameras",
        json={"camera_ids": []},
    )
    data = resp.json()
    assert data["success"] is False


# ---------------------------------------------------------------------------
# GET /api/partitions/{id}/state
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_partition_state_no_cameras(client, db_session):
    """State endpoint returns partition state with empty camera list."""
    part = await _make_partition(db_session, name="Empty Partition", state="armed")
    await db_session.commit()

    resp = await client.get(f"/api/partitions/{part.id}/state")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    state = data["data"]
    assert state["partition_id"] == str(part.id)
    assert state["state"] == "armed"
    assert state["cameras"] == []


@pytest.mark.asyncio
async def test_get_partition_state_not_found(client, db_session):
    """State endpoint returns error for non-existent partition."""
    fake_id = uuid.uuid4()
    resp = await client.get(f"/api/partitions/{fake_id}/state")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert "not found" in data["error"].lower()


@pytest.mark.asyncio
async def test_get_partition_state_with_cameras_and_refcount(client, db_session):
    """State endpoint includes per-camera detection snapshot and disarm refcounts."""
    from app.partitions.models import (
        CameraDetectionSnapshot,
        CameraDisarmRefcount,
    )

    loc = await _make_location(db_session)
    nvr = await _make_nvr(db_session, loc.id)
    cam = await _make_camera(db_session, nvr.id, channel_no=1)
    part = await _make_partition(db_session, location_id=loc.id, state="disarmed")
    db_session.add(PartitionCamera(partition_id=part.id, camera_id=cam.id))

    # Add a detection snapshot for this camera+partition
    snapshot_data = {"MotionDetection": "<xml>disabled</xml>"}
    db_session.add(
        CameraDetectionSnapshot(
            camera_id=cam.id,
            partition_id=part.id,
            snapshot_data=snapshot_data,
        )
    )

    # Add a disarm refcount
    db_session.add(
        CameraDisarmRefcount(
            camera_id=cam.id,
            disarmed_by_partitions=[part.id],
        )
    )

    await db_session.commit()

    resp = await client.get(f"/api/partitions/{part.id}/state")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    state = data["data"]
    assert state["state"] == "disarmed"
    assert len(state["cameras"]) == 1
    cam_state = state["cameras"][0]
    assert cam_state["id"] == str(cam.id)
    assert cam_state["detection_snapshot"] == snapshot_data
    assert str(part.id) in cam_state["disarmed_by_partitions"]
    assert cam_state["disarm_count"] == 1


@pytest.mark.asyncio
async def test_get_partition_state_camera_no_snapshot(client, db_session):
    """State endpoint returns None for detection_snapshot if camera is armed (no snapshot)."""
    loc = await _make_location(db_session)
    nvr = await _make_nvr(db_session, loc.id)
    cam = await _make_camera(db_session, nvr.id, channel_no=2)
    part = await _make_partition(db_session, location_id=loc.id, state="armed")
    db_session.add(PartitionCamera(partition_id=part.id, camera_id=cam.id))
    await db_session.commit()

    resp = await client.get(f"/api/partitions/{part.id}/state")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    cam_state = data["data"]["cameras"][0]
    assert cam_state["detection_snapshot"] is None
    assert cam_state["disarmed_by_partitions"] == []
    assert cam_state["disarm_count"] == 0


# ---------------------------------------------------------------------------
# GET /api/partitions/{id}/audit
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_partition_audit_empty(client, db_session):
    """Audit endpoint returns empty paginated result for new partition."""
    part = await _make_partition(db_session)
    await db_session.commit()

    resp = await client.get(f"/api/partitions/{part.id}/audit")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    audit = data["data"]
    assert audit["total"] == 0
    assert audit["items"] == []
    assert audit["limit"] == 20
    assert audit["offset"] == 0


@pytest.mark.asyncio
async def test_get_partition_audit_not_found(client, db_session):
    """Audit endpoint returns error for non-existent partition."""
    fake_id = uuid.uuid4()
    resp = await client.get(f"/api/partitions/{fake_id}/audit")
    data = resp.json()
    assert data["success"] is False
    assert "not found" in data["error"].lower()


@pytest.mark.asyncio
async def test_get_partition_audit_with_entries(client, db_session):
    """Audit endpoint returns log entries with correct fields."""
    from app.partitions.models import PartitionAuditLog

    part = await _make_partition(db_session)

    # Add audit log entries
    db_session.add(PartitionAuditLog(
        partition_id=part.id,
        action="disarm",
        performed_by="operator1",
        audit_metadata={"reason": "maintenance"},
    ))
    db_session.add(PartitionAuditLog(
        partition_id=part.id,
        action="arm",
        performed_by="operator2",
        audit_metadata={"cameras_restored": 2},
    ))
    await db_session.commit()

    resp = await client.get(f"/api/partitions/{part.id}/audit")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    audit = data["data"]
    assert audit["total"] == 2
    assert len(audit["items"]) == 2
    actions = {item["action"] for item in audit["items"]}
    assert actions == {"arm", "disarm"}
    performers = {item["performed_by"] for item in audit["items"]}
    assert performers == {"operator1", "operator2"}
    disarm_entry = next(i for i in audit["items"] if i["action"] == "disarm")
    assert disarm_entry["audit_metadata"] == {"reason": "maintenance"}


@pytest.mark.asyncio
async def test_get_partition_audit_pagination(client, db_session):
    """Audit endpoint supports limit and offset for pagination."""
    from app.partitions.models import PartitionAuditLog

    part = await _make_partition(db_session)

    # Create 5 audit entries
    for i in range(5):
        db_session.add(PartitionAuditLog(
            partition_id=part.id,
            action=f"action_{i}",
            performed_by="tester",
        ))
    await db_session.commit()

    # Request first page
    resp = await client.get(f"/api/partitions/{part.id}/audit?limit=2&offset=0")
    assert resp.status_code == 200
    data = resp.json()
    audit = data["data"]
    assert audit["total"] == 5
    assert audit["limit"] == 2
    assert audit["offset"] == 0
    assert len(audit["items"]) == 2

    # Request second page
    resp2 = await client.get(f"/api/partitions/{part.id}/audit?limit=2&offset=2")
    data2 = resp2.json()
    audit2 = data2["data"]
    assert audit2["total"] == 5
    assert audit2["limit"] == 2
    assert audit2["offset"] == 2
    assert len(audit2["items"]) == 2

    # Third page (1 item)
    resp3 = await client.get(f"/api/partitions/{part.id}/audit?limit=2&offset=4")
    data3 = resp3.json()
    audit3 = data3["data"]
    assert audit3["total"] == 5
    assert len(audit3["items"]) == 1


@pytest.mark.asyncio
async def test_get_partition_audit_different_partitions_isolated(client, db_session):
    """Audit log only returns entries for the requested partition."""
    from app.partitions.models import PartitionAuditLog

    part1 = await _make_partition(db_session, name="Partition 1")
    part2 = await _make_partition(db_session, name="Partition 2")

    db_session.add(PartitionAuditLog(
        partition_id=part1.id,
        action="disarm",
        performed_by="user_a",
    ))
    db_session.add(PartitionAuditLog(
        partition_id=part2.id,
        action="arm",
        performed_by="user_b",
    ))
    await db_session.commit()

    resp = await client.get(f"/api/partitions/{part1.id}/audit")
    data = resp.json()
    assert data["success"] is True
    audit = data["data"]
    assert audit["total"] == 1
    assert audit["items"][0]["action"] == "disarm"
    assert audit["items"][0]["partition_id"] == str(part1.id)


# ---------------------------------------------------------------------------
# Arm / Disarm envelope verification
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_disarm_returns_api_response_envelope(client, db_session):
    """POST /disarm returns APIResponse envelope with success and data fields."""
    part = await _make_partition(db_session, name="Disarm Test", state="armed")
    await db_session.commit()

    resp = await client.post(
        f"/api/partitions/{part.id}/disarm",
        json={"disarmed_by": "tester", "reason": "test"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "success" in data
    assert data["success"] is True
    assert "data" in data
    # No cameras in partition — should disarm cleanly
    assert data["data"]["cameras_disarmed"] == 0


@pytest.mark.asyncio
async def test_arm_returns_api_response_envelope(client, db_session):
    """POST /arm returns APIResponse envelope with success and data fields."""
    part = await _make_partition(db_session, name="Arm Test", state="disarmed")
    await db_session.commit()

    resp = await client.post(
        f"/api/partitions/{part.id}/arm",
        json={"armed_by": "tester"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "success" in data
    assert data["success"] is True
    assert "data" in data
    assert data["data"]["cameras_restored"] == 0


@pytest.mark.asyncio
async def test_disarm_not_found_returns_error_envelope(client, db_session):
    """POST /disarm on non-existent partition returns APIResponse with success=False."""
    fake_id = uuid.uuid4()
    resp = await client.post(
        f"/api/partitions/{fake_id}/disarm",
        json={"disarmed_by": "tester"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert data["error"] is not None
