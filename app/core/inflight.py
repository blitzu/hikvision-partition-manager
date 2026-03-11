"""In-flight ISAPI call counter for graceful shutdown drain.

Tracks the number of active ISAPI calls so that the lifespan shutdown hook
can wait for all in-flight requests to complete before disposing the engine.

Design notes:
- asyncio.Event() is created lazily (inside the running event loop) to avoid
  the DeprecationWarning raised by Python 3.10+ when an Event is created at
  module import time outside of any running loop.
- The _state dict is intentionally simple (not thread-safe with a lock) because
  all ISAPI calls run in the asyncio event loop on a single thread.

Usage:
    from app.core import inflight

    # In ISAPIClient methods:
    async with track_inflight():
        ...

    # In lifespan shutdown:
    remaining = await inflight.wait_drain(timeout=30.0)
"""
import asyncio
from contextlib import asynccontextmanager

_state: dict = {"count": 0, "event": None}


def _get_event() -> asyncio.Event:
    """Lazily create asyncio.Event inside the running event loop."""
    if _state["event"] is None:
        _state["event"] = asyncio.Event()
        _state["event"].set()  # starts idle (no in-flight calls)
    return _state["event"]


def increment() -> None:
    """Mark one ISAPI call as in-flight."""
    _state["count"] += 1
    _get_event().clear()


def decrement() -> None:
    """Mark one ISAPI call as completed."""
    _state["count"] -= 1
    if _state["count"] <= 0:
        _state["count"] = 0
        _get_event().set()


async def wait_drain(timeout: float = 30.0) -> int:
    """Wait for all in-flight ISAPI calls to complete.

    Returns:
        0 if all calls completed within timeout.
        Remaining count (> 0) if timeout elapsed.
    """
    try:
        await asyncio.wait_for(_get_event().wait(), timeout=timeout)
        return 0
    except asyncio.TimeoutError:
        return _state["count"]


@asynccontextmanager
async def track_inflight():
    """Async context manager: increment on enter, decrement on exit."""
    increment()
    try:
        yield
    finally:
        decrement()


def reset() -> None:
    """Reset state to zero. Use in tests only."""
    _state["count"] = 0
    _state["event"] = None
