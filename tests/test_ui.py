"""Integration tests for Phase 5 UI routes.

Covers UI-01 (Dashboard), UI-02 (Partition Detail), UI-03 (Partition Form),
and UI-04 (NVR Management) requirements via HTTP-level integration tests.

All tests use the `client` and `db_session` fixtures from conftest.py.
The `mock_scheduler_calls` fixture is autouse across the test suite.
"""
import uuid

import pytest

from app.cameras.models import Camera
from app.core.crypto import encrypt_password
from app.locations.models import Location
from app.nvrs.models import NVRDevice
from app.partitions.models import (
    CameraDetectionSnapshot,
    CameraDisarmRefcount,
    Partition,
    PartitionCamera,
    PartitionState,
)
from tests.mocks import MockISAPIClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_isapi(monkeypatch):
    monkeypatch.setattr("app.partitions.service.ISAPIClient", MockISAPIClient)


async def _make_full_partition(db, state="armed"):
    """Create Location -> NVR -> Camera -> Partition -> PartitionCamera -> PartitionState."""
    loc = Location(name="L", timezone="UTC")
    db.add(loc)
    await db.flush()

    nvr = NVRDevice(
        location_id=loc.id,
        name="N",
        ip_address="1.2.3.4",
        port=80,
        username="u",
        password_encrypted=encrypt_password("p"),
        status="unknown",
    )
    db.add(nvr)
    await db.flush()

    cam = Camera(nvr_id=nvr.id, channel_no=1)
    db.add(cam)
    await db.flush()

    part = Partition(name="Test Partition")
    db.add(part)
    await db.flush()

    db.add(PartitionCamera(partition_id=part.id, camera_id=cam.id))
    db.add(PartitionState(partition_id=part.id, state=state))
    await db.commit()

    return part, cam


async def _add_disarmed_snapshots(db, cam, part):
    """Add CameraDetectionSnapshot and CameraDisarmRefcount for a disarmed state."""
    db.add(
        CameraDetectionSnapshot(
            camera_id=cam.id,
            partition_id=part.id,
            snapshot_data={"MotionDetection": "<xml/>"},
        )
    )
    db.add(
        CameraDisarmRefcount(
            camera_id=cam.id,
            disarmed_by_partitions=[part.id],
        )
    )
    await db.commit()


# ---------------------------------------------------------------------------
# UI-01: Dashboard (GAP-1 through GAP-5)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dashboard_returns_200_html(client, db_session):
    """GAP-1: GET / with no data returns 200 with HTML content-type and Dashboard heading."""
    resp = await client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "Dashboard" in resp.text


@pytest.mark.asyncio
async def test_dashboard_contains_htmx_polling(client, db_session):
    """GAP-2: GET / response body includes HTMX polling attribute 'every 10s'."""
    resp = await client.get("/")
    assert resp.status_code == 200
    assert "every 10s" in resp.text


@pytest.mark.asyncio
async def test_partitions_partial_returns_html(client, db_session):
    """GAP-3: GET /partitions-partial returns 200 with text/html content-type."""
    resp = await client.get("/partitions-partial")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


@pytest.mark.asyncio
async def test_disarm_row_returns_html_tr(client, db_session, mock_isapi):
    """GAP-4: POST /ui/partitions/{id}/disarm-row returns 200 HTML containing a <tr element."""
    part, _cam = await _make_full_partition(db_session, state="armed")

    resp = await client.post(
        f"/ui/partitions/{part.id}/disarm-row",
        data={"disarmed_by": "operator"},
    )
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "<tr" in resp.text


@pytest.mark.asyncio
async def test_arm_row_returns_html_tr(client, db_session, mock_isapi):
    """GAP-5: POST /ui/partitions/{id}/arm-row returns 200 HTML containing a <tr element."""
    part, cam = await _make_full_partition(db_session, state="disarmed")
    await _add_disarmed_snapshots(db_session, cam, part)

    resp = await client.post(
        f"/ui/partitions/{part.id}/arm-row",
        data={"armed_by": "operator"},
    )
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "<tr" in resp.text


# ---------------------------------------------------------------------------
# UI-02: Partition Detail (GAP-6 through GAP-10)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_partition_detail_returns_200_html(client, db_session):
    """GAP-6: GET /partitions/{id} returns 200 HTML containing the partition name."""
    part = Partition(name="My Test Zone")
    db_session.add(part)
    await db_session.flush()
    db_session.add(PartitionState(partition_id=part.id, state="armed"))
    await db_session.commit()

    resp = await client.get(f"/partitions/{part.id}")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "My Test Zone" in resp.text


@pytest.mark.asyncio
async def test_partition_detail_404_for_unknown(client, db_session):
    """GAP-7: GET /partitions/{random_uuid} returns 404 HTML response."""
    random_id = uuid.uuid4()
    resp = await client.get(f"/partitions/{random_id}")
    assert resp.status_code == 404
    assert "text/html" in resp.headers["content-type"]


@pytest.mark.asyncio
async def test_partition_detail_partial_returns_html(client, db_session):
    """GAP-8: GET /ui/partitions/{id}/detail-partial returns 200 HTML."""
    part = Partition(name="Detail Partial Zone")
    db_session.add(part)
    await db_session.flush()
    db_session.add(PartitionState(partition_id=part.id, state="armed"))
    await db_session.commit()

    resp = await client.get(f"/ui/partitions/{part.id}/detail-partial")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


@pytest.mark.asyncio
async def test_disarm_detail_returns_html_body(client, db_session, mock_isapi):
    """GAP-9: POST /ui/partitions/{id}/disarm-detail returns 200 HTML."""
    part, _cam = await _make_full_partition(db_session, state="armed")

    resp = await client.post(
        f"/ui/partitions/{part.id}/disarm-detail",
        data={"disarmed_by": "operator"},
    )
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


@pytest.mark.asyncio
async def test_arm_detail_returns_html_body(client, db_session, mock_isapi):
    """GAP-10: POST /ui/partitions/{id}/arm-detail returns 200 HTML."""
    part, cam = await _make_full_partition(db_session, state="disarmed")
    await _add_disarmed_snapshots(db_session, cam, part)

    resp = await client.post(
        f"/ui/partitions/{part.id}/arm-detail",
        data={"armed_by": "operator"},
    )
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


# ---------------------------------------------------------------------------
# UI-03: Partition Form (GAP-11 through GAP-13)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_partition_new_form_returns_html_with_form_fields(client, db_session):
    """GAP-11: GET /partitions/new returns 200 HTML with <form and name= input."""
    resp = await client.get("/partitions/new")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "<form" in resp.text
    assert "name=" in resp.text


@pytest.mark.asyncio
async def test_partition_edit_form_returns_html_prefilled(client, db_session):
    """GAP-12: GET /partitions/{id}/edit returns 200 HTML containing the partition name."""
    part = Partition(name="Editable Zone")
    db_session.add(part)
    await db_session.flush()
    db_session.add(PartitionState(partition_id=part.id, state="armed"))
    await db_session.commit()

    resp = await client.get(f"/partitions/{part.id}/edit")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "Editable Zone" in resp.text


@pytest.mark.asyncio
async def test_partition_create_redirects_on_success(client, db_session):
    """GAP-13: POST /ui/partitions/create redirects 303 to /partitions/{id}."""
    resp = await client.post(
        "/ui/partitions/create",
        data={"name": "Test Partition"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "location" in resp.headers
    assert "/partitions/" in resp.headers["location"]


# ---------------------------------------------------------------------------
# UI-04: NVR Management (GAP-14 through GAP-15)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_nvrs_page_returns_200_html(client, db_session):
    """GAP-14: GET /nvrs with no data returns 200 HTML containing 'NVR'."""
    resp = await client.get("/nvrs")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "NVR" in resp.text


@pytest.mark.asyncio
async def test_nvr_detail_partial_returns_html(client, db_session):
    """GAP-15: GET /ui/nvrs/{nvr_id}/detail returns 200 HTML."""
    loc = Location(name="Site A", timezone="UTC")
    db_session.add(loc)
    await db_session.flush()

    nvr = NVRDevice(
        location_id=loc.id,
        name="Main NVR",
        ip_address="10.0.0.1",
        port=80,
        username="admin",
        password_encrypted=encrypt_password("secret"),
        status="unknown",
    )
    db_session.add(nvr)
    await db_session.commit()

    resp = await client.get(f"/ui/nvrs/{nvr.id}/detail")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
