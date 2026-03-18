"""Structured JSON logging for the Hikvision Partition Manager.

JsonFormatter: formats every log record as a single-line JSON object.
FileLogHandler: appends log records to LOG_FILE as JSON lines for /admin/logs.
setup_logging: configures the root logger with JsonFormatter on StreamHandler.

NVR-06 security: password fields are scrubbed from all log output.
"""
import datetime
import json
import logging
import traceback

# Standard LogRecord instance attributes — excluded from the "extra" fields display
_SKIP_ATTRS: frozenset = frozenset({
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "message", "asctime", "taskName",
})


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


LOG_FILE = "/tmp/app.log"
_MAX_LINES = 500


class FileLogHandler(logging.Handler):
    """Appends log records to LOG_FILE as JSON lines."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            ts = datetime.datetime.fromtimestamp(record.created).strftime("%Y-%m-%dT%H:%M:%S")
            entry = {
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
                entry["exception"] = "".join(traceback.format_exception(*record.exc_info))
            with open(LOG_FILE, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            self.handleError(record)


# Keep memory_handler name for backwards compat with imports
memory_handler = FileLogHandler()


def read_log_records(max_lines: int = _MAX_LINES) -> list[dict]:
    """Read the last max_lines records from the log file."""
    try:
        with open(LOG_FILE) as f:
            lines = f.readlines()
        records = []
        for line in reversed(lines[-max_lines:]):
            try:
                records.append(json.loads(line))
            except Exception:
                pass
        return records
    except FileNotFoundError:
        return []


def setup_logging(log_level: str = "INFO") -> None:
    """Configure root logger to emit structured JSON to stderr + log file."""
    formatter = JsonFormatter()
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logging.basicConfig(level=log_level.upper(), handlers=[stream_handler, memory_handler], force=True)
