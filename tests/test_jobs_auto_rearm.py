"""Unit tests for app/jobs/auto_rearm.py — schedule, cancel, fire, and webhook logic.

All tests use mocking/monkeypatching — no real DB or APScheduler instance needed.
"""
import asyncio
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# schedule_rearm tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_schedule_rearm_adds_job_with_correct_id(monkeypatch):
    """schedule_rearm should call add_schedule with id='rearm:{partition_id}'."""
    from app.jobs import auto_rearm

    partition_id = uuid.uuid4()
    run_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    mock_scheduler = MagicMock()
    mock_scheduler.add_schedule = AsyncMock(return_value="schedule-id")
    monkeypatch.setattr(auto_rearm, "scheduler", mock_scheduler)

    await auto_rearm.schedule_rearm(partition_id, run_at)

    mock_scheduler.add_schedule.assert_called_once()
    call_kwargs = mock_scheduler.add_schedule.call_args

    # First positional arg is the job function
    assert call_kwargs.args[0] is auto_rearm.auto_rearm_job

    # id keyword arg must be "rearm:{partition_id}"
    assert call_kwargs.kwargs.get("id") == f"rearm:{partition_id}"

    # kwargs for the job function must include partition_id_str
    job_kwargs = call_kwargs.kwargs.get("kwargs", {})
    assert job_kwargs.get("partition_id_str") == str(partition_id)


@pytest.mark.asyncio
async def test_schedule_rearm_replaces_existing_job(monkeypatch):
    """schedule_rearm should use replace conflict policy so re-scheduling works."""
    from app.jobs import auto_rearm
    from apscheduler import ConflictPolicy

    partition_id = uuid.uuid4()
    run_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    mock_scheduler = MagicMock()
    mock_scheduler.add_schedule = AsyncMock(return_value="schedule-id")
    monkeypatch.setattr(auto_rearm, "scheduler", mock_scheduler)

    await auto_rearm.schedule_rearm(partition_id, run_at)

    call_kwargs = mock_scheduler.add_schedule.call_args.kwargs
    assert call_kwargs.get("conflict_policy") == ConflictPolicy.replace


# ---------------------------------------------------------------------------
# cancel_rearm tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancel_rearm_removes_schedule_by_correct_id(monkeypatch):
    """cancel_rearm should call remove_schedule with id='rearm:{partition_id}'."""
    from app.jobs import auto_rearm

    partition_id = uuid.uuid4()

    mock_scheduler = MagicMock()
    mock_scheduler.remove_schedule = AsyncMock()
    monkeypatch.setattr(auto_rearm, "scheduler", mock_scheduler)

    await auto_rearm.cancel_rearm(partition_id)

    mock_scheduler.remove_schedule.assert_called_once_with(f"rearm:{partition_id}")


@pytest.mark.asyncio
async def test_cancel_rearm_no_op_when_schedule_not_found(monkeypatch):
    """cancel_rearm should silently swallow ScheduleLookupError."""
    from app.jobs import auto_rearm
    from apscheduler import ScheduleLookupError

    partition_id = uuid.uuid4()

    mock_scheduler = MagicMock()
    mock_scheduler.remove_schedule = AsyncMock(
        side_effect=ScheduleLookupError(str(partition_id))
    )
    monkeypatch.setattr(auto_rearm, "scheduler", mock_scheduler)

    # Should not raise
    await auto_rearm.cancel_rearm(partition_id)


# ---------------------------------------------------------------------------
# auto_rearm_job tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auto_rearm_job_calls_arm_partition_with_system_performed_by(monkeypatch):
    """auto_rearm_job should call arm_partition with performed_by='system:auto_rearm'."""
    from app.jobs import auto_rearm

    partition_id = uuid.uuid4()
    partition_id_str = str(partition_id)

    mock_arm = AsyncMock(return_value=MagicMock(cameras_restored=1, cameras_kept_disarmed=0))

    mock_db = AsyncMock()
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)

    mock_partition = MagicMock()
    mock_partition.name = "Test Partition"
    mock_db.get = AsyncMock(return_value=mock_partition)

    mock_session_factory = MagicMock(return_value=mock_db)

    with patch("app.partitions.service.arm_partition", mock_arm):
        with patch.object(auto_rearm, "async_session_factory", mock_session_factory):
            await auto_rearm.auto_rearm_job(partition_id_str)

    # Verify arm_partition was called with correct performed_by
    mock_arm.assert_called_once()
    call_args = mock_arm.call_args
    assert call_args.args[0] == partition_id  # partition_id as UUID
    assert call_args.args[1] == "system:auto_rearm"  # performed_by


@pytest.mark.asyncio
async def test_auto_rearm_job_fires_webhook_as_task(monkeypatch):
    """auto_rearm_job should fire deliver_webhook as asyncio.create_task."""
    from app.jobs import auto_rearm

    partition_id = uuid.uuid4()
    partition_id_str = str(partition_id)

    mock_arm = AsyncMock(return_value=MagicMock(cameras_restored=1))

    mock_db = AsyncMock()
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)

    mock_partition = MagicMock()
    mock_partition.name = "Test Partition"
    mock_db.get = AsyncMock(return_value=mock_partition)

    mock_session_factory = MagicMock(return_value=mock_db)

    webhook_payloads = []

    async def fake_deliver_webhook(payload):
        webhook_payloads.append(payload)

    with patch("app.partitions.service.arm_partition", mock_arm):
        with patch.object(auto_rearm, "async_session_factory", mock_session_factory):
            with patch.object(auto_rearm, "deliver_webhook", fake_deliver_webhook):
                await auto_rearm.auto_rearm_job(partition_id_str)
                # Give any create_task time to run
                await asyncio.sleep(0.01)

    assert len(webhook_payloads) == 1
    payload = webhook_payloads[0]
    assert payload["type"] == "auto_rearmed"
    assert payload["partition_id"] == str(partition_id)


# ---------------------------------------------------------------------------
# deliver_webhook tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deliver_webhook_succeeds_on_first_attempt(monkeypatch):
    """deliver_webhook should POST payload and return on success."""
    from app.jobs import auto_rearm

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("httpx.AsyncClient", return_value=mock_client):
        with patch.object(auto_rearm, "settings") as mock_settings:
            mock_settings.ALERT_WEBHOOK_URL = "http://example.com/webhook"
            await auto_rearm.deliver_webhook({"type": "auto_rearmed", "partition_id": "abc"})

    mock_client.post.assert_called_once()
    mock_response.raise_for_status.assert_called_once()


@pytest.mark.asyncio
async def test_deliver_webhook_retries_on_failure_and_succeeds(monkeypatch):
    """deliver_webhook should retry up to 3x and succeed on a later attempt."""
    from app.jobs import auto_rearm

    call_count = 0

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()

    async def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise Exception("Connection refused")
        return mock_response

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = mock_post

    with patch("httpx.AsyncClient", return_value=mock_client):
        with patch.object(auto_rearm, "settings") as mock_settings:
            mock_settings.ALERT_WEBHOOK_URL = "http://example.com/webhook"
            with patch("asyncio.sleep", AsyncMock()):
                await auto_rearm.deliver_webhook({"type": "auto_rearmed", "partition_id": "abc"})

    assert call_count == 3


@pytest.mark.asyncio
async def test_deliver_webhook_gives_up_after_3_retries(monkeypatch):
    """deliver_webhook should give up after 3 retries and log, never raise."""
    from app.jobs import auto_rearm

    call_count = 0

    async def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        raise Exception("Connection refused")

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = mock_post

    with patch("httpx.AsyncClient", return_value=mock_client):
        with patch.object(auto_rearm, "settings") as mock_settings:
            mock_settings.ALERT_WEBHOOK_URL = "http://example.com/webhook"
            with patch("asyncio.sleep", AsyncMock()):
                # Should not raise
                await auto_rearm.deliver_webhook({"type": "auto_rearmed", "partition_id": "abc"})

    # 1 initial + 3 retries = 4 total attempts
    assert call_count == 4


@pytest.mark.asyncio
async def test_deliver_webhook_no_op_when_url_not_configured(monkeypatch):
    """deliver_webhook should return immediately if ALERT_WEBHOOK_URL is not set."""
    from app.jobs import auto_rearm

    with patch.object(auto_rearm, "settings") as mock_settings:
        mock_settings.ALERT_WEBHOOK_URL = None
        with patch("httpx.AsyncClient") as mock_client_cls:
            await auto_rearm.deliver_webhook({"type": "test"})
            mock_client_cls.assert_not_called()
