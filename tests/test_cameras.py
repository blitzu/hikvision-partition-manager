"""Tests for camera sync endpoint.

Covers NVR-04 (camera upsert idempotency) and
NVR-05 (last_seen_at updated after sync).
"""
import uuid

import httpx
import pytest
from sqlalchemy import select

from app.cameras.models import Camera
from app.nvrs.models import NVRDevice


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

NVR_PAYLOAD = {
    "name": "Main NVR",
    "ip_address": "192.168.1.100",
    "port": 8000,
    "username": "admin",
    "password": "testpassword",
}


async def _create_location(client, name="Test Site", timezone="UTC") -> str:
    """Helper: create a location and return its id."""
    resp = await client.post(
        "/api/locations",
        json={"name": name, "timezone": timezone},
    )
    assert resp.status_code == 200
    return resp.json()["data"]["id"]


async def _create_nvr(client, loc_id: str) -> str:
    """Helper: create an NVR and return its id."""
    resp = await client.post(
        f"/api/locations/{loc_id}/nvrs",
        json=NVR_PAYLOAD,
    )
    assert resp.status_code == 200
    return resp.json()["data"]["id"]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_creates_cameras(client, monkeypatch):
    """GET /api/nvrs/{id}/cameras/sync returns 200, success=true, 2 cameras."""
    from tests.mocks import MockISAPIClient
    import app.cameras.routes as cam_routes

    monkeypatch.setattr(cam_routes, "ISAPIClient", lambda *args, **kwargs: MockISAPIClient())

    loc_id = await _create_location(client)
    nvr_id = await _create_nvr(client, loc_id)

    response = await client.get(f"/api/nvrs/{nvr_id}/cameras/sync")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"] is not None
    assert len(body["data"]) == 2


@pytest.mark.asyncio
async def test_sync_upsert_no_duplicates(client, db_session, monkeypatch):
    """Calling sync twice produces exactly 2 camera records in DB (upsert idempotency)."""
    from tests.mocks import MockISAPIClient
    import app.cameras.routes as cam_routes

    monkeypatch.setattr(cam_routes, "ISAPIClient", lambda *args, **kwargs: MockISAPIClient())

    loc_id = await _create_location(client)
    nvr_id = await _create_nvr(client, loc_id)

    # Sync twice
    await client.get(f"/api/nvrs/{nvr_id}/cameras/sync")
    await client.get(f"/api/nvrs/{nvr_id}/cameras/sync")

    # Query DB directly — must have exactly 2 cameras
    result = await db_session.execute(
        select(Camera).where(Camera.nvr_id == uuid.UUID(nvr_id))
    )
    cameras = result.scalars().all()
    assert len(cameras) == 2


@pytest.mark.asyncio
async def test_sync_updates_existing_name(client, db_session, monkeypatch):
    """Second sync with updated name overwrites the camera name in DB."""
    import app.cameras.routes as cam_routes

    call_count = 0

    class UpdatingMockISAPIClient:
        async def get_camera_channels(self):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [{"channel_no": 1, "name": "Camera 1"}, {"channel_no": 2, "name": "Camera 2"}]
            else:
                return [{"channel_no": 1, "name": "Camera 1 Updated"}, {"channel_no": 2, "name": "Camera 2"}]

    monkeypatch.setattr(cam_routes, "ISAPIClient", lambda *args, **kwargs: UpdatingMockISAPIClient())

    loc_id = await _create_location(client)
    nvr_id = await _create_nvr(client, loc_id)

    await client.get(f"/api/nvrs/{nvr_id}/cameras/sync")
    await client.get(f"/api/nvrs/{nvr_id}/cameras/sync")

    result = await db_session.execute(
        select(Camera).where(
            Camera.nvr_id == uuid.UUID(nvr_id),
            Camera.channel_no == 1,
        )
    )
    cam = result.scalars().first()
    assert cam is not None
    assert cam.name == "Camera 1 Updated"


@pytest.mark.asyncio
async def test_sync_updates_last_seen_at(client, db_session, monkeypatch):
    """After successful sync, NVR last_seen_at is set and status='online'."""
    from tests.mocks import MockISAPIClient
    import app.cameras.routes as cam_routes

    monkeypatch.setattr(cam_routes, "ISAPIClient", lambda *args, **kwargs: MockISAPIClient())

    loc_id = await _create_location(client)
    nvr_id = await _create_nvr(client, loc_id)

    await client.get(f"/api/nvrs/{nvr_id}/cameras/sync")

    nvr = (await db_session.execute(
        select(NVRDevice).where(NVRDevice.id == uuid.UUID(nvr_id))
    )).scalars().first()
    assert nvr.last_seen_at is not None
    assert nvr.status == "online"


@pytest.mark.asyncio
async def test_sync_unknown_nvr(client):
    """GET /api/nvrs/{unknown_uuid}/cameras/sync returns 200, success=false, not found."""
    unknown_id = str(uuid.uuid4())
    response = await client.get(f"/api/nvrs/{unknown_id}/cameras/sync")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["error"] is not None
    assert "not found" in body["error"].lower()


@pytest.mark.asyncio
async def test_sync_isapi_failure(client, monkeypatch):
    """ISAPI exception returns 200, success=false, no 500 error."""
    import app.cameras.routes as cam_routes

    class FailingISAPIClient:
        async def get_camera_channels(self):
            raise httpx.ConnectError("Connection refused")

    monkeypatch.setattr(cam_routes, "ISAPIClient", lambda *args, **kwargs: FailingISAPIClient())

    loc_id = await _create_location(client)
    nvr_id = await _create_nvr(client, loc_id)

    response = await client.get(f"/api/nvrs/{nvr_id}/cameras/sync")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["error"] is not None
    assert len(body["error"]) > 0
