import json
import logging

from app.logging_setup import JsonFormatter, RequestContextFilter, clear_log_context, set_log_context


def test_json_formatter_includes_request_context_fields() -> None:
    clear_log_context()
    set_log_context(request_id="req-123", client_ip="127.0.0.1", user_id=42, path="/health", method="GET")

    record = logging.makeLogRecord(
        {
            "name": "app.test",
            "levelno": logging.INFO,
            "levelname": "INFO",
            "msg": "structured message",
        }
    )
    RequestContextFilter().filter(record)
    payload = json.loads(JsonFormatter().format(record))

    assert payload["message"] == "structured message"
    assert payload["extra"]["request_id"] == "req-123"
    assert payload["extra"]["client_ip"] == "127.0.0.1"
    assert payload["extra"]["user_id"] == 42
    assert payload["extra"]["path"] == "/health"
    assert payload["extra"]["method"] == "GET"

    clear_log_context()
