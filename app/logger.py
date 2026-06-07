"""Structured logging wrapper over loguru.

All app logging goes through `log_*` (CLAUDE.md § Style: no `print`). Messages are
brace-escaped so a literal `{}` never triggers a loguru format KeyError (invariant #8).

# Adapted from ai-factory/core/logger.py
# Reason: reuse the log_info/log_warning/log_error(message, component, action, ctx)
# signature + brace-escaping; loguru markup `<...>` is inert with colors disabled.
"""

from typing import Any

from loguru import logger


def _safe(text: object) -> str:
    """Escape braces so loguru does not treat them as format fields."""
    return str(text).replace("{", "{{").replace("}", "}}")


def _emit(level: str, message: str, component: str, action: str, context: dict[str, Any] | None) -> None:
    logger.bind(component=component, action=action, context=context or {}).log(level, _safe(message))


def log_info(message: str, component: str, action: str, context: dict[str, Any] | None = None) -> None:
    _emit("INFO", message, component, action, context)


def log_warning(message: str, component: str, action: str, context: dict[str, Any] | None = None) -> None:
    _emit("WARNING", message, component, action, context)


def log_error(message: str, component: str, action: str, context: dict[str, Any] | None = None) -> None:
    _emit("ERROR", message, component, action, context)


def log_debug(message: str, component: str, action: str, context: dict[str, Any] | None = None) -> None:
    _emit("DEBUG", message, component, action, context)
