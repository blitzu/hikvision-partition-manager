"""Tests for NVR CRUD endpoints.

Covers NVR-02 (NVR creation with encrypted passwords) and
NVR-06 (password never returned in API responses).
"""
import uuid

import pytest
from sqlalchemy import select

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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_nvr_success(client):
    """POST /api/locations/{id}/nvrs returns 200 with expected fields."""
    loc_id = await _create_location(client)
    response = await client.post(
        f"/api/locations/{loc_id}/nvrs",
        json=NVR_PAYLOAD,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    data = body["data"]
    assert "id" in data
    assert data["name"] == "Main NVR"
    assert data["ip_address"] == "192.168.1.100"
    assert data["port"] == 8000
    assert data["username"] == "admin"
    assert data["location_id"] == loc_id


@pytest.mark.asyncio
async def test_password_encrypted_in_db(client, db_session):
    """After NVR creation, password_encrypted in DB must differ from plaintext."""
    loc_id = await _create_location(client)
    await client.post(f"/api/locations/{loc_id}/nvrs", json=NVR_PAYLOAD)

    nvr = (await db_session.execute(select(NVRDevice))).scalars().first()
    assert nvr is not None
    assert nvr.password_encrypted != "testpassword"
    assert "testpassword" not in nvr.password_encrypted


@pytest.mark.asyncio
async def test_password_not_in_response(client):
    """The plaintext password must not appear anywhere in the response text."""
    loc_id = await _create_location(client)
    response = await client.post(f"/api/locations/{loc_id}/nvrs", json=NVR_PAYLOAD)
    assert "testpassword" not in response.text


@pytest.mark.asyncio
async def test_password_encrypted_field_not_in_response(client):
    """Response data must have no 'password' or 'password_encrypted' key."""
    loc_id = await _create_location(client)
    response = await client.post(f"/api/locations/{loc_id}/nvrs", json=NVR_PAYLOAD)
    assert response.status_code == 200
    data = response.json()["data"]
    assert "password" not in data
    assert "password_encrypted" not in data


@pytest.mark.asyncio
async def test_list_nvrs_for_location(client):
    """GET /api/locations/{id}/nvrs returns list containing the created NVR."""
    loc_id = await _create_location(client)
    await client.post(f"/api/locations/{loc_id}/nvrs", json=NVR_PAYLOAD)

    response = await client.get(f"/api/locations/{loc_id}/nvrs")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert isinstance(body["data"], list)
    assert len(body["data"]) == 1
    assert body["data"][0]["name"] == "Main NVR"


@pytest.mark.asyncio
async def test_nvr_linked_to_location(client):
    """Created NVR data.location_id must equal the location id used in URL."""
    loc_id = await _create_location(client)
    response = await client.post(f"/api/locations/{loc_id}/nvrs", json=NVR_PAYLOAD)
    assert response.json()["data"]["location_id"] == loc_id


@pytest.mark.asyncio
async def test_create_nvr_unknown_location(client):
    """POST to unknown location returns 200 with success=false and error message."""
    unknown_id = str(uuid.uuid4())
    response = await client.post(
        f"/api/locations/{unknown_id}/nvrs",
        json=NVR_PAYLOAD,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["error"] is not None
    assert "not found" in body["error"].lower()
