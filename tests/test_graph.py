"""Graph wiring tests: routing, idempotency, drop path, graceful degradation.

Uses injected fake LLM callables (DI at the graph boundary) + real mock adapters /
audit on tmp paths. Marked `mock_llm` (CLAUDE.md): LLM behaviour is substituted.
"""

from pathlib import Path

import pytest

from app.adapters.notify import MockNotifyAdapter
from app.adapters.ticket import MockTicketAdapter
from app.graph.build import run_monitor
from app.graph.deps import GraphDeps
from app.state import (
    FeedEntry,
    MonitorState,
    OwnerInfo,
    PlanOutput,
    RagContext,
    Severity,
    Status,
    TriageOutput,
)
from app.store.audit import AuditStore

pytestmark = pytest.mark.mock_llm


def _deps(tmp_path: Path, *, is_incident: bool = True, context_empty: bool = False) -> GraphDeps:
    def fake_triage(entry: FeedEntry) -> TriageOutput:
        return TriageOutput(
            is_incident=is_incident,
            severity=Severity.HIGH if is_incident else Severity.INFO,
            topic="платежи",
            affected_system="payment-gateway",
        )

    def fake_retrieve(query: str) -> RagContext:
        if context_empty:
            return RagContext(chunks=[], context_empty=True)
        return RagContext(chunks=["runbook: рестартовать поды"], context_empty=False)

    def fake_resolve(system: str) -> OwnerInfo:
        return OwnerInfo(affected_system=system, owner_name="Иван", owner_email="ivan@bank.local", team="payments")

    def fake_plan(entry: FeedEntry, ctx: RagContext) -> PlanOutput:
        return PlanOutput(summary="рост 5xx", recommendations=["рестарт", "проверить БД"], escalate_to="payments")

    return GraphDeps(
        triage=fake_triage,
        retrieve=fake_retrieve,
        resolve_owner=fake_resolve,
        plan=fake_plan,
        ticket=MockTicketAdapter(db_path=tmp_path / "tickets.db"),
        notify=MockNotifyAdapter(outbox_dir=tmp_path / "outbox"),
        audit=AuditStore(db_path=tmp_path / "audit.db"),
    )


def _entry() -> FeedEntry:
    return FeedEntry(entry_id="demo-001", title="Платёжный шлюз", body="рост 5xx", source="fake")


def test_happy_path_incident(tmp_path: Path) -> None:
    deps = _deps(tmp_path)
    result = run_monitor(MonitorState(raw_entry=_entry()), deps=deps)

    assert result.status is Status.DONE
    assert result.ticket_id == "DEMO-001"
    assert result.notified is True
    assert (tmp_path / "outbox" / "demo-001.eml").exists()

    records = deps.audit.list_records()
    assert len(records) == 1 and records[0].status is Status.DONE


def test_drop_path_non_incident(tmp_path: Path) -> None:
    deps = _deps(tmp_path, is_incident=False)
    result = run_monitor(MonitorState(raw_entry=_entry()), deps=deps)

    assert result.status is Status.DROPPED
    assert result.ticket_id is None
    assert result.notified is False
    assert not (tmp_path / "outbox").exists() or not list((tmp_path / "outbox").glob("*.eml"))

    records = deps.audit.list_records()
    assert len(records) == 1 and records[0].status is Status.DROPPED


def test_idempotent_repeat_does_not_duplicate(tmp_path: Path) -> None:
    deps = _deps(tmp_path)
    first = run_monitor(MonitorState(raw_entry=_entry()), deps=deps)
    second = run_monitor(MonitorState(raw_entry=_entry()), deps=deps)

    assert first.ticket_id == second.ticket_id == "DEMO-001"
    assert second.status is Status.DONE
    assert len(list((tmp_path / "outbox").glob("*.eml"))) == 1  # no second email
    assert len(deps.audit.list_records()) == 1  # single audit row


def test_graceful_empty_context_still_completes(tmp_path: Path) -> None:
    deps = _deps(tmp_path, context_empty=True)
    result = run_monitor(MonitorState(raw_entry=_entry()), deps=deps)
    assert result.status is Status.DONE
    assert result.ticket_id == "DEMO-001"
