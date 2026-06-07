"""Structured-output schemas + a robust JSON fallback parser.

`TriageOutput` / `PlanOutput` are defined canonically in `app.state` (CLAUDE.md
§ Style: shared models live there) and re-exported here so callers import them from
the llm layer. Both are flat — GigaChat-safe (invariant #5) — and are bound to the
model via `llm.with_structured_output(...)` in the graph nodes.

`parse_model` is the fallback for the rare case the model returns prose around the
JSON instead of a clean structured object (ARCHITECTURE § Промпт-инжиниринг).
"""

import json
from typing import Any

from pydantic import BaseModel, ValidationError

from app.state import PlanOutput, TriageOutput

__all__ = ["PlanOutput", "TriageOutput", "extract_json", "parse_model"]


def extract_json(raw: str) -> dict[str, Any] | None:
    """Return the first JSON object found in `raw`, or None.

    Locates the first '{' and decodes from there, ignoring any trailing text
    (handles ```json fences and prose around the object).
    """
    start = raw.find("{")
    if start == -1:
        return None
    try:
        obj, _ = json.JSONDecoder().raw_decode(raw[start:])
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def parse_model[T: BaseModel](raw: str, model: type[T]) -> T | None:
    """Best-effort parse of `raw` into `model`; returns None if it can't be validated."""
    data = extract_json(raw)
    if data is None:
        return None
    try:
        return model.model_validate(data)
    except ValidationError:
        return None
