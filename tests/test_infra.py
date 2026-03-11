"""Infrastructure tests: JSON logging, request middleware, graceful shutdown drain.

Covers INFRA-03 (.env.example), INFRA-04 (graceful shutdown), INFRA-05 (JSON logging),
INFRA-06 (request_id injection and access log).
"""
import asyncio
import json
import logging
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from app.core import inflight
from app.core.logging import JsonFormatter
from app.middleware.logging import RequestLoggingMiddleware, request_id_var


# ---------------------------------------------------------------------------
# INFRA-05: JSON formatter
# ---------------------------------------------------------------------------


def _make_record(msg: str, **extra) -> logging.LogRecord:
    """Helper: build a LogRecord with optional extra fields."""
    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg=msg,
        args=(),
        exc_info=None,
    )
    for key, val in extra.items():
        setattr(record, key, val)
    return record


def test_json_formatter():
    """JsonFormatter.format() returns valid JSON with required keys."""
    formatter = JsonFormatter()
    record = _make_record("hello world")
    output = formatter.format(record)
    obj = json.loads(output)

    assert "timestamp" in obj
    assert obj["level"] == "INFO"
    assert obj["logger"] == "test.logger"
    assert obj["message"] == "hello world"
    assert "request_id" in obj


def test_json_formatter_extra_fields():
    """Extra fields passed via extra= appear in JSON output."""
    formatter = JsonFormatter()
    record = _make_record("disarm started", component="partition", event="disarm_start")
    output = formatter.format(record)
    obj = json.loads(output)

    assert obj.get("component") == "partition"
    assert obj.get("event") == "disarm_start"


def test_json_formatter_no_password():
    """Password field is scrubbed from log output."""
    formatter = JsonFormatter()
    record = _make_record("nvr connect", password="secret")
    output = formatter.format(record)

    assert "secret" not in output
    obj = json.loads(output)
    assert "password" not in obj


# ---------------------------------------------------------------------------
# INFRA-06: Request logging middleware
# ---------------------------------------------------------------------------


def test_access_log_middleware():
    """RequestLoggingMiddleware emits a log record for each request.

    Uses a manual handler attached to the 'http' logger because TestClient
    runs the ASGI app in a worker thread (anyio portal), outside caplog's
    propagation chain.
    """
    app = FastAPI()
    app.add_middleware(RequestLoggingMiddleware)

    @app.get("/ping")
    def ping():
        return {"ok": True}

    captured: list[logging.LogRecord] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            captured.append(record)

    handler = _Capture()
    http_logger = logging.getLogger("http")
    http_logger.addHandler(handler)
    http_logger.setLevel(logging.INFO)

    try:
        with TestClient(app) as client:
            resp = client.get("/ping")
    finally:
        http_logger.removeHandler(handler)

    assert resp.status_code == 200
    assert len(captured) >= 1, "Expected at least one 'http' log record"
    rec = captured[0]
    assert getattr(rec, "component", None) == "http"
    assert getattr(rec, "method", None) == "GET"
    assert getattr(rec, "path", None) == "/ping"
    assert getattr(rec, "status_code", None) == 200
    assert hasattr(rec, "duration_ms")


def test_request_id_set():
    """request_id_var is set to a non-empty UUID during dispatch."""
    captured = {}

    app = FastAPI()
    app.add_middleware(RequestLoggingMiddleware)

    @app.get("/check-rid")
    def check_rid():
        captured["rid"] = request_id_var.get("")
        return {"rid": captured["rid"]}

    with TestClient(app) as client:
        resp = client.get("/check-rid")

    assert resp.status_code == 200
    assert len(captured.get("rid", "")) == 36  # UUID4 is 36 chars with dashes


# ---------------------------------------------------------------------------
# INFRA-04: Graceful shutdown drain
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_graceful_shutdown_drain():
    """wait_drain blocks until all decrement() calls complete, then returns 0."""
    inflight.reset()

    N = 5
    for _ in range(N):
        inflight.increment()

    async def finish_one():
        await asyncio.sleep(0.01)
        inflight.decrement()

    tasks = [asyncio.create_task(finish_one()) for _ in range(N)]
    remaining = await inflight.wait_drain(timeout=2.0)
    await asyncio.gather(*tasks)

    assert remaining == 0


@pytest.mark.asyncio
async def test_graceful_shutdown_timeout():
    """wait_drain returns remaining count > 0 when timeout elapses without drain."""
    inflight.reset()

    inflight.increment()  # never decremented
    remaining = await inflight.wait_drain(timeout=0.05)

    assert remaining > 0
    inflight.reset()  # teardown


# ---------------------------------------------------------------------------
# INFRA-03: .env.example completeness
# ---------------------------------------------------------------------------


def test_env_example_has_all_vars():
    """.env.example contains all 6 required environment variable keys."""
    required = {
        "DATABASE_URL",
        "ENCRYPTION_KEY",
        "BASE_URL",
        "LOG_LEVEL",
        "ALERT_WEBHOOK_URL",
        "POLL_INTERVAL_SECONDS",
    }
    with open(".env.example") as f:
        content = f.read()

    for var in required:
        assert var in content, f"Missing required var in .env.example: {var}"
