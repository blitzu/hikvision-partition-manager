"""Unit tests for app/jobs/monitors.py — stuck-disarmed and NVR health check jobs.

Tests use AsyncMock/MagicMock for DB session, ISAPIClient, and deliver_webhook.
Module-level state (_nvr_prev_status, _nvr_last_offline_alert) is reset
between tests via monkeypatching or direct dict clearing.
"""
import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_partition(
    partition_id=None,
    name="Zone A",
    alert_if_disarmed_minutes=30,
    deleted_at=None,
):
    p = MagicMock()
    p.id = partition_id or uuid.uuid4()
    p.name = name
    p.alert_if_disarmed_minutes = alert_if_disarmed_minutes
    p.deleted_at = deleted_at
    return p


def _make_state(
    partition_id=None,
    state="disarmed",
    last_changed_at=None,
    last_changed_by="user:alice",
    scheduled_rearm_at=None,
):
    s = MagicMock()
    s.partition_id = partition_id or uuid.uuid4()
    s.state = state
    s.last_changed_at = last_changed_at or datetime.now(timezone.utc) - timedelta(hours=2)
    s.last_changed_by = last_changed_by
    s.scheduled_rearm_at = scheduled_rearm_at
    return s


def _make_nvr(
    nvr_id=None,
    name="NVR-01",
    ip_address="192.168.1.100",
    port=8000,
    username="admin",
    password_encrypted="enc_pw",
    status="online",
    location_name="Main Building",
):
    nvr = MagicMock()
    nvr.id = nvr_id or uuid.uuid4()
    nvr.name = name
    nvr.ip_address = ip_address
    nvr.port = port
    nvr.username = username
    nvr.password_encrypted = password_encrypted
    nvr.status = status
    nvr.last_seen_at = None
    return nvr, location_name


def _make_db_session():
    """Build a mock async DB session context manager."""
    db = AsyncMock()
    db.__aenter__ = AsyncMock(return_value=db)
    db.__aexit__ = AsyncMock(return_value=False)
    db.commit = AsyncMock()
    return db


# ---------------------------------------------------------------------------
# stuck_disarmed_monitor tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stuck_disarmed_monitor_fires_webhook_for_overdue_partition():
    """stuck_disarmed_monitor should fire partition_stuck_disarmed webhook for an overdue partition."""
    from app.jobs import monitors

    partition_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    disarmed_at = now - timedelta(minutes=60)  # 60 min ago

    partition = _make_partition(partition_id=partition_id, alert_if_disarmed_minutes=30)
    state = _make_state(
        partition_id=partition_id,
        last_changed_at=disarmed_at,
        last_changed_by="user:alice",
        scheduled_rearm_at=None,
    )

    db = _make_db_session()
    mock_result = MagicMock()
    mock_result.all.return_value = [(partition, state)]
    db.execute = AsyncMock(return_value=mock_result)

    webhook_payloads = []

    async def fake_deliver_webhook(payload):
        webhook_payloads.append(payload)

    with patch.object(monitors, "async_session_factory", return_value=db):
        with patch.object(monitors, "deliver_webhook", fake_deliver_webhook):
            with patch("asyncio.create_task", side_effect=asyncio.ensure_future):
                await monitors.stuck_disarmed_monitor()
                await asyncio.sleep(0.01)

    assert len(webhook_payloads) == 1
    payload = webhook_payloads[0]
    assert payload["type"] == "partition_stuck_disarmed"
    assert payload["partition_id"] == str(partition_id)
    assert payload["partition_name"] == partition.name
    assert payload["disarmed_by"] == "user:alice"
    assert payload["disarmed_at"] == disarmed_at.isoformat()
    assert payload["minutes_elapsed"] >= 60.0
    assert payload["scheduled_rearm_at"] is None


@pytest.mark.asyncio
async def test_stuck_disarmed_monitor_skips_non_overdue_partition():
    """stuck_disarmed_monitor should skip partitions that are not yet overdue."""
    from app.jobs import monitors

    partition_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    disarmed_at = now - timedelta(minutes=10)  # Only 10 minutes ago

    partition = _make_partition(partition_id=partition_id, alert_if_disarmed_minutes=30)
    state = _make_state(
        partition_id=partition_id,
        last_changed_at=disarmed_at,
    )

    db = _make_db_session()
    mock_result = MagicMock()
    mock_result.all.return_value = [(partition, state)]
    db.execute = AsyncMock(return_value=mock_result)

    webhook_payloads = []

    async def fake_deliver_webhook(payload):
        webhook_payloads.append(payload)

    with patch.object(monitors, "async_session_factory", return_value=db):
        with patch.object(monitors, "deliver_webhook", fake_deliver_webhook):
            await monitors.stuck_disarmed_monitor()

    assert len(webhook_payloads) == 0


@pytest.mark.asyncio
async def test_stuck_disarmed_monitor_skips_partitions_without_alert_threshold():
    """stuck_disarmed_monitor should only query partitions with alert_if_disarmed_minutes set.

    The query filters on IS NOT NULL so no rows with NULL threshold are returned.
    This test verifies that if an empty result is returned, no webhooks fire.
    """
    from app.jobs import monitors

    db = _make_db_session()
    mock_result = MagicMock()
    mock_result.all.return_value = []  # DB filtered them out already
    db.execute = AsyncMock(return_value=mock_result)

    webhook_payloads = []

    async def fake_deliver_webhook(payload):
        webhook_payloads.append(payload)

    with patch.object(monitors, "async_session_factory", return_value=db):
        with patch.object(monitors, "deliver_webhook", fake_deliver_webhook):
            await monitors.stuck_disarmed_monitor()

    assert len(webhook_payloads) == 0


@pytest.mark.asyncio
async def test_stuck_disarmed_monitor_fires_multiple_webhooks_per_cycle():
    """stuck_disarmed_monitor fires one webhook per overdue partition per cycle."""
    from app.jobs import monitors

    now = datetime.now(timezone.utc)
    p1_id = uuid.uuid4()
    p2_id = uuid.uuid4()

    partition1 = _make_partition(partition_id=p1_id, name="Zone A", alert_if_disarmed_minutes=20)
    state1 = _make_state(partition_id=p1_id, last_changed_at=now - timedelta(minutes=30))

    partition2 = _make_partition(partition_id=p2_id, name="Zone B", alert_if_disarmed_minutes=15)
    state2 = _make_state(partition_id=p2_id, last_changed_at=now - timedelta(minutes=25))

    db = _make_db_session()
    mock_result = MagicMock()
    mock_result.all.return_value = [(partition1, state1), (partition2, state2)]
    db.execute = AsyncMock(return_value=mock_result)

    webhook_payloads = []

    async def fake_deliver_webhook(payload):
        webhook_payloads.append(payload)

    with patch.object(monitors, "async_session_factory", return_value=db):
        with patch.object(monitors, "deliver_webhook", fake_deliver_webhook):
            with patch("asyncio.create_task", side_effect=asyncio.ensure_future):
                await monitors.stuck_disarmed_monitor()
                await asyncio.sleep(0.01)

    assert len(webhook_payloads) == 2
    partition_ids = {p["partition_id"] for p in webhook_payloads}
    assert str(p1_id) in partition_ids
    assert str(p2_id) in partition_ids


# ---------------------------------------------------------------------------
# nvr_health_check tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_nvr_health_check_fires_nvr_offline_on_first_failure():
    """nvr_health_check should fire nvr_offline webhook when NVR goes offline for the first time."""
    from app.jobs import monitors

    # Reset module-level state
    monitors._nvr_prev_status.clear()
    monitors._nvr_last_offline_alert.clear()

    nvr_id = uuid.uuid4()
    nvr, location_name = _make_nvr(nvr_id=nvr_id, status="online")

    db = _make_db_session()
    mock_result = MagicMock()
    mock_result.all.return_value = [(nvr, location_name)]
    db.execute = AsyncMock(return_value=mock_result)

    webhook_payloads = []

    async def fake_deliver_webhook(payload):
        webhook_payloads.append(payload)

    mock_client = AsyncMock()
    mock_client.get_device_info = AsyncMock(side_effect=Exception("Connection refused"))

    with patch.object(monitors, "async_session_factory", return_value=db):
        with patch.object(monitors, "deliver_webhook", fake_deliver_webhook):
            with patch.object(monitors, "ISAPIClient", return_value=mock_client):
                with patch.object(monitors, "decrypt_password", return_value="plaintext"):
                    with patch("asyncio.create_task", side_effect=asyncio.ensure_future):
                        await monitors.nvr_health_check()
                        await asyncio.sleep(0.01)

    assert len(webhook_payloads) == 1
    payload = webhook_payloads[0]
    assert payload["type"] == "nvr_offline"
    assert payload["nvr_id"] == str(nvr_id)
    assert payload["nvr_name"] == nvr.name
    assert payload["location_name"] == location_name

    # NVR status should be updated to 'offline'
    assert nvr.status == "offline"


@pytest.mark.asyncio
async def test_nvr_health_check_suppresses_offline_within_cooldown():
    """nvr_health_check should NOT fire nvr_offline webhook if already alerted within 5 minutes."""
    from app.jobs import monitors

    monitors._nvr_prev_status.clear()
    monitors._nvr_last_offline_alert.clear()

    nvr_id = uuid.uuid4()
    nvr, location_name = _make_nvr(nvr_id=nvr_id, status="offline")

    # Simulate a previous offline alert 2 minutes ago (within cooldown)
    recent_alert_time = datetime.now(timezone.utc) - timedelta(minutes=2)
    monitors._nvr_prev_status[nvr_id] = "offline"
    monitors._nvr_last_offline_alert[nvr_id] = recent_alert_time

    db = _make_db_session()
    mock_result = MagicMock()
    mock_result.all.return_value = [(nvr, location_name)]
    db.execute = AsyncMock(return_value=mock_result)

    webhook_payloads = []

    async def fake_deliver_webhook(payload):
        webhook_payloads.append(payload)

    mock_client = AsyncMock()
    mock_client.get_device_info = AsyncMock(side_effect=Exception("Still offline"))

    with patch.object(monitors, "async_session_factory", return_value=db):
        with patch.object(monitors, "deliver_webhook", fake_deliver_webhook):
            with patch.object(monitors, "ISAPIClient", return_value=mock_client):
                with patch.object(monitors, "decrypt_password", return_value="plaintext"):
                    await monitors.nvr_health_check()
                    await asyncio.sleep(0.01)

    # Should be suppressed — no webhook
    assert len(webhook_payloads) == 0


@pytest.mark.asyncio
async def test_nvr_health_check_fires_offline_again_after_cooldown_expires():
    """nvr_health_check should fire nvr_offline webhook again after 5-minute cooldown passes."""
    from app.jobs import monitors

    monitors._nvr_prev_status.clear()
    monitors._nvr_last_offline_alert.clear()

    nvr_id = uuid.uuid4()
    nvr, location_name = _make_nvr(nvr_id=nvr_id, status="offline")

    # Simulate a previous offline alert 10 minutes ago (outside cooldown)
    old_alert_time = datetime.now(timezone.utc) - timedelta(minutes=10)
    monitors._nvr_prev_status[nvr_id] = "offline"
    monitors._nvr_last_offline_alert[nvr_id] = old_alert_time

    db = _make_db_session()
    mock_result = MagicMock()
    mock_result.all.return_value = [(nvr, location_name)]
    db.execute = AsyncMock(return_value=mock_result)

    webhook_payloads = []

    async def fake_deliver_webhook(payload):
        webhook_payloads.append(payload)

    mock_client = AsyncMock()
    mock_client.get_device_info = AsyncMock(side_effect=Exception("Still offline"))

    with patch.object(monitors, "async_session_factory", return_value=db):
        with patch.object(monitors, "deliver_webhook", fake_deliver_webhook):
            with patch.object(monitors, "ISAPIClient", return_value=mock_client):
                with patch.object(monitors, "decrypt_password", return_value="plaintext"):
                    with patch("asyncio.create_task", side_effect=asyncio.ensure_future):
                        await monitors.nvr_health_check()
                        await asyncio.sleep(0.01)

    # Cooldown expired — should fire again
    assert len(webhook_payloads) == 1
    assert webhook_payloads[0]["type"] == "nvr_offline"


@pytest.mark.asyncio
async def test_nvr_health_check_fires_nvr_online_on_recovery():
    """nvr_health_check should fire nvr_online webhook when NVR recovers from offline."""
    from app.jobs import monitors

    monitors._nvr_prev_status.clear()
    monitors._nvr_last_offline_alert.clear()

    nvr_id = uuid.uuid4()
    nvr, location_name = _make_nvr(nvr_id=nvr_id, status="offline")

    # NVR was previously offline
    monitors._nvr_prev_status[nvr_id] = "offline"

    db = _make_db_session()
    mock_result = MagicMock()
    mock_result.all.return_value = [(nvr, location_name)]
    db.execute = AsyncMock(return_value=mock_result)

    webhook_payloads = []

    async def fake_deliver_webhook(payload):
        webhook_payloads.append(payload)

    mock_client = AsyncMock()
    mock_client.get_device_info = AsyncMock(return_value={"deviceName": "NVR-01"})

    with patch.object(monitors, "async_session_factory", return_value=db):
        with patch.object(monitors, "deliver_webhook", fake_deliver_webhook):
            with patch.object(monitors, "ISAPIClient", return_value=mock_client):
                with patch.object(monitors, "decrypt_password", return_value="plaintext"):
                    with patch("asyncio.create_task", side_effect=asyncio.ensure_future):
                        await monitors.nvr_health_check()
                        await asyncio.sleep(0.01)

    assert len(webhook_payloads) == 1
    payload = webhook_payloads[0]
    assert payload["type"] == "nvr_online"
    assert payload["nvr_id"] == str(nvr_id)
    assert payload["nvr_name"] == nvr.name
    assert payload["location_name"] == location_name

    # NVR status should be updated to 'online'
    assert nvr.status == "online"


@pytest.mark.asyncio
async def test_nvr_health_check_no_webhook_when_stable_online():
    """nvr_health_check should fire no webhook when NVR stays online."""
    from app.jobs import monitors

    monitors._nvr_prev_status.clear()
    monitors._nvr_last_offline_alert.clear()

    nvr_id = uuid.uuid4()
    nvr, location_name = _make_nvr(nvr_id=nvr_id, status="online")

    # NVR was previously online
    monitors._nvr_prev_status[nvr_id] = "online"

    db = _make_db_session()
    mock_result = MagicMock()
    mock_result.all.return_value = [(nvr, location_name)]
    db.execute = AsyncMock(return_value=mock_result)

    webhook_payloads = []

    async def fake_deliver_webhook(payload):
        webhook_payloads.append(payload)

    mock_client = AsyncMock()
    mock_client.get_device_info = AsyncMock(return_value={"deviceName": "NVR-01"})

    with patch.object(monitors, "async_session_factory", return_value=db):
        with patch.object(monitors, "deliver_webhook", fake_deliver_webhook):
            with patch.object(monitors, "ISAPIClient", return_value=mock_client):
                with patch.object(monitors, "decrypt_password", return_value="plaintext"):
                    await monitors.nvr_health_check()

    assert len(webhook_payloads) == 0


@pytest.mark.asyncio
async def test_nvr_health_check_updates_last_seen_at_on_success():
    """nvr_health_check should set last_seen_at on successful health check."""
    from app.jobs import monitors

    monitors._nvr_prev_status.clear()
    monitors._nvr_last_offline_alert.clear()

    nvr_id = uuid.uuid4()
    nvr, location_name = _make_nvr(nvr_id=nvr_id, status="online")
    monitors._nvr_prev_status[nvr_id] = "online"

    db = _make_db_session()
    mock_result = MagicMock()
    mock_result.all.return_value = [(nvr, location_name)]
    db.execute = AsyncMock(return_value=mock_result)

    mock_client = AsyncMock()
    mock_client.get_device_info = AsyncMock(return_value={"deviceName": "NVR-01"})

    with patch.object(monitors, "async_session_factory", return_value=db):
        with patch.object(monitors, "deliver_webhook", AsyncMock()):
            with patch.object(monitors, "ISAPIClient", return_value=mock_client):
                with patch.object(monitors, "decrypt_password", return_value="plaintext"):
                    await monitors.nvr_health_check()

    # last_seen_at should be updated
    assert nvr.last_seen_at is not None


@pytest.mark.asyncio
async def test_nvr_health_check_commits_after_all_nvrs_processed():
    """nvr_health_check should commit DB changes after processing all NVRs."""
    from app.jobs import monitors

    monitors._nvr_prev_status.clear()
    monitors._nvr_last_offline_alert.clear()

    nvr_id = uuid.uuid4()
    nvr, location_name = _make_nvr(nvr_id=nvr_id, status="online")
    monitors._nvr_prev_status[nvr_id] = "online"

    db = _make_db_session()
    mock_result = MagicMock()
    mock_result.all.return_value = [(nvr, location_name)]
    db.execute = AsyncMock(return_value=mock_result)

    mock_client = AsyncMock()
    mock_client.get_device_info = AsyncMock(return_value={"deviceName": "NVR-01"})

    with patch.object(monitors, "async_session_factory", return_value=db):
        with patch.object(monitors, "deliver_webhook", AsyncMock()):
            with patch.object(monitors, "ISAPIClient", return_value=mock_client):
                with patch.object(monitors, "decrypt_password", return_value="plaintext"):
                    await monitors.nvr_health_check()

    db.commit.assert_called_once()


# ---------------------------------------------------------------------------
# Lifespan job registration tests (JOB-02, JOB-03)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lifespan_registers_stuck_disarmed_monitor_with_5_minute_interval():
    """JOB-02: The stuck-disarmed monitor must be registered with IntervalTrigger(minutes=5)."""
    from apscheduler import ConflictPolicy
    from apscheduler.triggers.interval import IntervalTrigger
    from app.jobs.monitors import stuck_disarmed_monitor

    add_schedule_calls = []

    mock_scheduler = MagicMock()

    async def fake_add_schedule(func, trigger, id, conflict_policy):
        add_schedule_calls.append({
            "func": func,
            "trigger": trigger,
            "id": id,
            "conflict_policy": conflict_policy,
        })

    mock_scheduler.add_schedule = fake_add_schedule
    mock_scheduler.start_in_background = AsyncMock()
    mock_scheduler.__aenter__ = AsyncMock(return_value=mock_scheduler)
    mock_scheduler.__aexit__ = AsyncMock(return_value=False)

    # Patch all blocking dependencies so lifespan proceeds without real DB/scheduler
    mock_db = AsyncMock()
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(return_value=mock_result)

    with patch("app.main.scheduler", mock_scheduler):
        with patch("app.main.asyncio.to_thread", AsyncMock()):
            with patch("app.main.async_session_factory", return_value=mock_db):
                with patch("app.main.wait_drain", AsyncMock(return_value=0)):
                    with patch("app.main.engine") as mock_engine:
                        mock_engine.dispose = AsyncMock()
                        # Drive the lifespan context manager through startup
                        from app.main import lifespan, app as fastapi_app
                        async with lifespan(fastapi_app):
                            pass

    # Find the call that registered stuck_disarmed_monitor
    stuck_call = next(
        (c for c in add_schedule_calls if c["func"] is stuck_disarmed_monitor),
        None,
    )
    assert stuck_call is not None, "stuck_disarmed_monitor was not registered"
    assert stuck_call["id"] == "stuck_disarmed_monitor"
    assert stuck_call["conflict_policy"] == ConflictPolicy.replace

    trigger = stuck_call["trigger"]
    assert isinstance(trigger, IntervalTrigger), f"Expected IntervalTrigger, got {type(trigger)}"
    # IntervalTrigger exposes interval components as direct attributes
    assert trigger.minutes == 5, f"Expected minutes=5, got {trigger.minutes}"


@pytest.mark.asyncio
async def test_lifespan_registers_nvr_health_check_with_60_second_interval():
    """JOB-03: The NVR health check must be registered with IntervalTrigger(seconds=60)."""
    from apscheduler import ConflictPolicy
    from apscheduler.triggers.interval import IntervalTrigger
    from app.jobs.monitors import nvr_health_check

    add_schedule_calls = []

    mock_scheduler = MagicMock()

    async def fake_add_schedule(func, trigger, id, conflict_policy):
        add_schedule_calls.append({
            "func": func,
            "trigger": trigger,
            "id": id,
            "conflict_policy": conflict_policy,
        })

    mock_scheduler.add_schedule = fake_add_schedule
    mock_scheduler.start_in_background = AsyncMock()
    mock_scheduler.__aenter__ = AsyncMock(return_value=mock_scheduler)
    mock_scheduler.__aexit__ = AsyncMock(return_value=False)

    mock_db = AsyncMock()
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(return_value=mock_result)

    with patch("app.main.scheduler", mock_scheduler):
        with patch("app.main.asyncio.to_thread", AsyncMock()):
            with patch("app.main.async_session_factory", return_value=mock_db):
                with patch("app.main.wait_drain", AsyncMock(return_value=0)):
                    with patch("app.main.engine") as mock_engine:
                        mock_engine.dispose = AsyncMock()
                        from app.main import lifespan, app as fastapi_app
                        async with lifespan(fastapi_app):
                            pass

    nvr_call = next(
        (c for c in add_schedule_calls if c["func"] is nvr_health_check),
        None,
    )
    assert nvr_call is not None, "nvr_health_check was not registered"
    assert nvr_call["id"] == "nvr_health_check"
    assert nvr_call["conflict_policy"] == ConflictPolicy.replace

    trigger = nvr_call["trigger"]
    assert isinstance(trigger, IntervalTrigger), f"Expected IntervalTrigger, got {type(trigger)}"
    # IntervalTrigger exposes interval components as direct attributes
    assert trigger.seconds == 60, f"Expected seconds=60, got {trigger.seconds}"
