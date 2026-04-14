import contextvars
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys
from datetime import datetime, timezone

_RESERVED_RECORD_ATTRS = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "message",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
    "taskName",
}

_LOG_CONTEXT: contextvars.ContextVar[dict[str, object]] = contextvars.ContextVar("wuhongai_log_context", default={})


def set_log_context(**values: object) -> None:
    merged = dict(_LOG_CONTEXT.get())
    merged.update(values)
    _LOG_CONTEXT.set(merged)


def clear_log_context() -> None:
    _LOG_CONTEXT.set({})


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        ctx = _LOG_CONTEXT.get()
        record.request_id = ctx.get("request_id")
        record.client_ip = ctx.get("client_ip")
        record.user_id = ctx.get("user_id")
        record.path = ctx.get("path")
        record.method = ctx.get("method")
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        extras: dict = {}
        for key, value in record.__dict__.items():
            if key in _RESERVED_RECORD_ATTRS or key.startswith("_"):
                continue
            extras[key] = value
        if extras:
            payload["extra"] = extras
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logging(level: int = logging.INFO) -> None:
    from app.config import get_settings

    settings = get_settings()
    root = logging.getLogger()
    if getattr(root, "_wuhongai_json_logging", False):
        root.setLevel(level)
        return

    for handler in list(root.handlers):
        root.removeHandler(handler)

    formatter = JsonFormatter()
    context_filter = RequestContextFilter()

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    stream_handler.addFilter(context_filter)
    root.addHandler(stream_handler)

    if settings.log_file_enabled:
        log_file = Path(settings.log_dir) / "app.log"
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max(int(settings.log_file_max_mb or 1), 1) * 1024 * 1024,
            backupCount=max(int(settings.log_file_backup_count or 1), 1),
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler.addFilter(context_filter)
        root.addHandler(file_handler)

    root.setLevel(level)
    root._wuhongai_json_logging = True  # type: ignore[attr-defined]
