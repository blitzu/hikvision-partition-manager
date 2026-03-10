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
