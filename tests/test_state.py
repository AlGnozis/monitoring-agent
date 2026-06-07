"""Unit tests for the data contract in app.state."""

from datetime import datetime

from app.state import (
    EventRecord,
    FeedEntry,
    MonitorState,
    OwnerInfo,
    PlanOutput,
    RagContext,
    Severity,
    Status,
    TriageOutput,
    compute_event_hash,
)


def _entry() -> FeedEntry:
    return FeedEntry(entry_id="demo-001", title="t", body="b", source="fake")


def test_enums_serialise_as_plain_strings() -> None:
    assert Severity.HIGH == "HIGH"
    assert Status.DONE == "DONE"
    assert [s.value for s in Severity] == ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]


def test_compute_event_hash_is_deterministic_and_hex64() -> None:
    h1 = compute_event_hash("fake", "demo-001")
    h2 = compute_event_hash("fake", "demo-001")
    assert h1 == h2
    assert len(h1) == 64 and all(c in "0123456789abcdef" for c in h1)


def test_compute_event_hash_differs_on_different_inputs() -> None:
    assert compute_event_hash("fake", "demo-001") != compute_event_hash("fake", "demo-002")


def test_monitor_state_defaults() -> None:
    state = MonitorState(raw_entry=_entry())
    assert state.event_hash is None
    assert state.status is Status.PENDING
    assert state.notified is False
    assert state.tokens == 0
    assert state.timings == {}
    assert state.triage is None and state.action_plan is None


def test_monitor_state_carries_stage_payloads() -> None:
    state = MonitorState(
        raw_entry=_entry(),
        event_hash=compute_event_hash("fake", "demo-001"),
        triage=TriageOutput(is_incident=True, severity=Severity.HIGH, topic="db", affected_system="payment-gw"),
        rag_context=RagContext(chunks=["runbook"], context_empty=False),
        owner=OwnerInfo(affected_system="payment-gw", owner_name="X", owner_email="x@bank", team="core"),
        action_plan=PlanOutput(summary="s", recommendations=["r1", "r2"], escalate_to="x@bank"),
    )
    assert state.triage is not None and state.triage.severity is Severity.HIGH
    assert state.rag_context is not None and state.rag_context.context_empty is False
    assert state.action_plan is not None and state.action_plan.recommendations == ["r1", "r2"]


def test_event_record_defaults() -> None:
    rec = EventRecord(event_hash="abc")
    assert rec.status is Status.PENDING
    assert rec.ticket_id is None
    assert rec.tokens_total == 0
    assert isinstance(rec.created_at, datetime)
