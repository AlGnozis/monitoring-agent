"""Unit tests for app.logger (brace-safe loguru wrapper)."""

from app.logger import log_debug, log_error, log_info, log_warning


def test_logging_is_brace_safe_and_never_raises() -> None:
    # literal braces in the message must not trigger a loguru format error
    log_info("value {x} and {}", "Test", "test.info", {"k": 1})
    log_warning("warn {y}", "Test", "test.warn")
    log_error("boom", "Test", "test.error", {"e": "x"})
    log_debug("dbg {z}", "Test", "test.debug")
