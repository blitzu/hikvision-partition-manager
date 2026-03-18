"""Structured JSON logging for the Hikvision Partition Manager.

JsonFormatter: formats every log record as a single-line JSON object.
MemoryLogHandler: keeps the last 500 records in memory for /admin/logs.
setup_logging: configures the root logger with JsonFormatter on StreamHandler.

NVR-06 security: password fields are scrubbed from all log output.
"""
import collections
import datetime
import json
import logging

# Standard LogRecord attributes — excluded from the "extra" fields display
_SKIP_ATTRS: frozenset = frozenset(logging.LogRecord.__dict__) | {
    "message", "asctime", "args", "msg", "taskName",
}


class JsonFormatter(logging.Formatter):
    """Log formatter that produces single-line JSON output."""

    def format(self, record: logging.LogRecord) -> str:
        from app.middleware.logging import request_id_var  # lazy to avoid circular import

        log_obj: dict = {
            "timestamp": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_var.get(""),
        }

        for key, val in record.__dict__.items():
            if key not in _SKIP_ATTRS:
                log_obj[key] = val

        log_obj.pop("password", None)

        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj, default=str)


class MemoryLogHandler(logging.Handler):
    """Keeps the last `maxlen` log records in memory for /admin/logs.

    Builds the entry dict directly from the LogRecord so it never
    depends on a formatter being set — avoids silent emit failures.
    """

    def __init__(self, maxlen: int = 500) -> None:
        super().__init__()
        self.records: collections.deque = collections.deque(maxlen=maxlen)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            ts = datetime.datetime.fromtimestamp(record.created).strftime("%Y-%m-%dT%H:%M:%S")
            entry: dict = {
                "timestamp": ts,
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            }
            for key, val in record.__dict__.items():
                if key not in _SKIP_ATTRS:
                    entry[key] = str(val)
            entry.pop("password", None)
            if record.exc_info:
                entry["exception"] = self.formatException(record.exc_info)
            self.records.appendleft(entry)
        except Exception:
            pass


memory_handler = MemoryLogHandler(maxlen=500)


def setup_logging(log_level: str = "INFO") -> None:
    """Configure root logger to emit structured JSON to stderr + memory."""
    formatter = JsonFormatter()
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logging.basicConfig(level=log_level.upper(), handlers=[stream_handler, memory_handler], force=True)
