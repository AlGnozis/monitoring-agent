"""Unit tests for app.llm.schemas (re-export + fallback parser)."""

from app import state
from app.llm import schemas
from app.llm.schemas import TriageOutput, extract_json, parse_model


def test_reexports_are_canonical_state_models() -> None:
    assert schemas.TriageOutput is state.TriageOutput
    assert schemas.PlanOutput is state.PlanOutput


def test_extract_json_plain() -> None:
    assert extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_with_prose_and_fence() -> None:
    raw = 'Вот результат:\n```json\n{"a": 1, "b": "x"}\n```\nготово'
    assert extract_json(raw) == {"a": 1, "b": "x"}


def test_extract_json_invalid_or_non_object() -> None:
    assert extract_json("no json here") is None
    assert extract_json("[1, 2, 3]") is None  # not an object


def test_parse_model_valid() -> None:
    raw = '{"is_incident": true, "severity": "HIGH", "topic": "БД", "affected_system": "abs"}'
    out = parse_model(raw, TriageOutput)
    assert out is not None
    assert out.is_incident is True
    assert out.severity == "HIGH"


def test_parse_model_invalid_returns_none() -> None:
    # bad severity value
    bad_severity = '{"is_incident": true, "severity": "URGENT", "topic": "x", "affected_system": "y"}'
    assert parse_model(bad_severity, TriageOutput) is None
    # missing fields
    assert parse_model('{"is_incident": true}', TriageOutput) is None
    # no json
    assert parse_model("totally not json", TriageOutput) is None
