"""HTTP request logging middleware.

Injects a UUID request_id into a ContextVar for each request so that
JsonFormatter can include it in every log line emitted during the request.

Emits an INFO access log record after each response with component, method,
path, status_code, duration_ms, and request_id.
"""
import logging
import time
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

request_id_var: ContextVar[str] = ContextVar("request_id", default="")

logger = logging.getLogger("http")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Starlette middleware that adds request_id and emits an access log line."""

    async def dispatch(self, request: Request, call_next):
        rid = str(uuid.uuid4())
        token = request_id_var.set(rid)
        start = time.monotonic()
        try:
            response = await call_next(request)
        finally:
            duration_ms = round((time.monotonic() - start) * 1000, 1)
            logger.info(
                "request",
                extra={
                    "component": "http",
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                    "request_id": rid,
                },
            )
            request_id_var.reset(token)
        return response
