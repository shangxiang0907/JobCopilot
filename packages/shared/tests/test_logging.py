"""Regression tests for the shared structlog configuration.

The original config mixed the stdlib-only `add_logger_name` processor into a
native PrintLogger pipeline, crashing every log call (and with it, every
exception handler) with AttributeError.
"""

import json

from jobcopilot_shared.logging import configure_logging, get_logger


def test_log_calls_do_not_crash_and_emit_json(capsys) -> None:  # type: ignore[no-untyped-def]
    configure_logging("test-service")
    log = get_logger("test.module")

    log.info("something_happened", foo="bar")
    log.warning("something_suspicious", code="x")

    lines = [json.loads(line) for line in capsys.readouterr().out.strip().splitlines()]
    assert len(lines) == 2

    info_entry = lines[0]
    assert info_entry["event"] == "something_happened"
    assert info_entry["level"] == "info"
    assert info_entry["foo"] == "bar"
    assert info_entry["logger"] == "test.module"
    assert info_entry["service"] == "test-service"
    # Request-context keys default to "-" outside a request
    assert info_entry["trace_id"] == "-"
    assert info_entry["tenant_id"] == "-"


def test_exception_logging_renders_traceback(capsys) -> None:  # type: ignore[no-untyped-def]
    configure_logging("test-service")
    log = get_logger("test.module")

    try:
        raise ValueError("boom")
    except ValueError:
        log.exception("unexpected_error")

    entry = json.loads(capsys.readouterr().out.strip())
    assert entry["event"] == "unexpected_error"
    assert entry["level"] == "error"
    assert "ValueError: boom" in entry["exception"]
