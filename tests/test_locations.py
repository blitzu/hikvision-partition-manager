"""Tests for Location CRUD endpoints.

Covers NVR-01 requirements:
- Create location with valid/invalid timezone
- List locations
- Response field validation
"""
import pytest


@pytest.mark.asyncio
async def test_create_location_valid(client):
    """POST /api/locations with valid data returns 200 and success=True."""
    response = await client.post(
        "/api/locations",
        json={"name": "HQ", "timezone": "Europe/Bucharest"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["name"] == "HQ"
    assert body["data"]["timezone"] == "Europe/Bucharest"
    assert "id" in body["data"]


@pytest.mark.asyncio
async def test_create_location_invalid_timezone(client):
    """POST /api/locations with invalid timezone returns 422."""
    response = await client.post(
        "/api/locations",
        json={"name": "HQ", "timezone": "Invalid/Zone"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_location_missing_name(client):
    """POST /api/locations without name returns 422."""
    response = await client.post(
        "/api/locations",
        json={"timezone": "UTC"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_locations_empty(client):
    """GET /api/locations with no locations returns empty list."""
    response = await client.get("/api/locations")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"] == []


@pytest.mark.asyncio
async def test_list_locations_after_create(client):
    """GET /api/locations after creating one returns list with 1 item."""
    await client.post(
        "/api/locations",
        json={"name": "Branch Office", "timezone": "UTC"},
    )
    response = await client.get("/api/locations")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert len(body["data"]) == 1
    assert body["data"][0]["name"] == "Branch Office"
    assert "id" in body["data"][0]


@pytest.mark.asyncio
async def test_location_response_has_no_unexpected_fields(client):
    """Location response data keys must be a subset of expected fields."""
    response = await client.post(
        "/api/locations",
        json={"name": "Test Site", "timezone": "America/New_York"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    allowed_keys = {"id", "name", "timezone", "created_at"}
    assert set(data.keys()).issubset(allowed_keys)
