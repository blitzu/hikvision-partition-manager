"""Structured JSON logging for the Hikvision Partition Manager.

JsonFormatter: formats every log record as a single-line JSON object.
MemoryLogHandler: keeps the last 500 records in memory for /admin/logs.
setup_logging: configures the root logger with JsonFormatter on StreamHandler.

NVR-06 security: password fields are scrubbed from all log output.
"""
import collections
import json
import logging


class JsonFormatter(logging.Formatter):
    """Log formatter that produces single-line JSON output.

    Required fields in every record:
      timestamp, level, logger, message, request_id

    Extra fields passed via extra={} are included unless they are internal
    LogRecord attributes. The 'password' key is always scrubbed (NVR-06).
    """

    # Attributes present on every LogRecord — omit from JSON output to
    # avoid noise. We combine the default __dict__ keys with a small set
    # of post-format keys that are added by the Formatter base class.
    SKIP_ATTRS: frozenset = frozenset(logging.LogRecord.__dict__) | {
        "message",
        "asctime",
        "args",
        "msg",
        "taskName",
    }

    def format(self, record: logging.LogRecord) -> str:
        from app.middleware.logging import request_id_var  # lazy to avoid circular import

        log_obj: dict = {
            "timestamp": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_var.get(""),
        }

        # Include any extra fields added by the caller
        for key, val in record.__dict__.items():
            if key not in self.SKIP_ATTRS:
                log_obj[key] = val

        # NVR-06: scrub password field from all log output
        log_obj.pop("password", None)

        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj, default=str)


class MemoryLogHandler(logging.Handler):
    """Keeps the last `maxlen` formatted log records in memory.

    Accessible via `memory_handler.records` — a deque of dicts.
    """

    def __init__(self, maxlen: int = 500) -> None:
        super().__init__()
        self.records: collections.deque = collections.deque(maxlen=maxlen)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.records.appendleft(json.loads(self.format(record)))
        except Exception:
            pass


memory_handler = MemoryLogHandler(maxlen=500)


def setup_logging(log_level: str = "INFO") -> None:
    """Configure root logger to emit structured JSON to stderr.

    Should be called once at application startup, before FastAPI instantiation.
    Uses force=True to replace any existing handlers.
    """
    formatter = JsonFormatter()
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    memory_handler.setFormatter(formatter)
    logging.basicConfig(level=log_level.upper(), handlers=[stream_handler, memory_handler], force=True)
