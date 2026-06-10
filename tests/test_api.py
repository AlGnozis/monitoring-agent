"""API tests via TestClient with overridden deps/source (no network, no GigaChat)."""

from collections.abc import Iterator
from pathlib import Path

import pytest
import requests
from fastapi.testclient import TestClient

from app.adapters.notify import MockNotifyAdapter
from app.adapters.ticket import MockTicketAdapter
from app.api.server import app, provide_deps, provide_source
from app.graph.deps import GraphDeps
from app.state import FeedEntry, OwnerInfo, PlanOutput, RagContext, Severity, TriageOutput
from app.store.audit import AuditStore

pytestmark = pytest.mark.mock_llm


def _fake_deps(tmp_path: Path) -> GraphDeps:
    def triage(entry: FeedEntry) -> tuple[TriageOutput, int]:
        out = TriageOutput(is_incident=True, severity=Severity.HIGH, topic="платежи", affected_system="payment-gateway")
        return out, 11

    def resolve(system: str) -> OwnerInfo:
        return OwnerInfo(affected_system=system, owner_name="Иван", owner_email="ivan@bank.local", team="payments")

    def plan(entry: FeedEntry, ctx: RagContext) -> tuple[PlanOutput, int]:
        out = PlanOutput(summary="рост 5xx", recommendations=["рестарт"], escalate_to="payments")
        return out, 7

    return GraphDeps(
        triage=triage,
        retrieve=lambda q: RagContext(chunks=["runbook"], context_empty=False),
        resolve_owner=resolve,
        plan=plan,
        ticket=MockTicketAdapter(db_path=tmp_path / "tickets.db"),
        notify=MockNotifyAdapter(outbox_dir=tmp_path / "outbox"),
        audit=AuditStore(db_path=tmp_path / "audit.db"),
    )


class _StubSource:
    def fetch(self) -> list[FeedEntry]:
        return [FeedEntry(entry_id="demo-001", title="Платёжный шлюз", body="рост 5xx", source="fake")]

    def get(self, entry_id: str) -> FeedEntry | None:
        return next((e for e in self.fetch() if e.entry_id == entry_id), None)


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    deps = _fake_deps(tmp_path)
    app.dependency_overrides[provide_deps] = lambda: deps
    app.dependency_overrides[provide_source] = lambda: _StubSource()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_trigger_ok(client: TestClient) -> None:
    resp = client.post("/trigger", json={"entry_id": "demo-001"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "DONE"
    assert body["ticket_id"] == "DEMO-001"
    assert body["event_hash"]


def test_trigger_not_found(client: TestClient) -> None:
    resp = client.post("/trigger", json={"entry_id": "nope"})
    assert resp.status_code == 404
    assert resp.json()["error"] == "entry_not_found"


def test_trigger_validation(client: TestClient) -> None:
    resp = client.post("/trigger", json={})
    assert resp.status_code == 422
    assert resp.json()["error"] == "validation"


def test_audit_list_and_get(client: TestClient) -> None:
    event_hash = client.post("/trigger", json={"entry_id": "demo-001"}).json()["event_hash"]

    listing = client.get("/audit").json()
    assert listing["total"] == 1
    assert listing["records"][0]["status"] == "DONE"

    detail = client.get(f"/audit/{event_hash}")
    assert detail.status_code == 200
    assert detail.json()["ticket_id"] == "DEMO-001"

    missing = client.get("/audit/unknownhash")
    assert missing.status_code == 404
    assert missing.json()["error"] == "not_found"


def test_health_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Resp:
        status_code = 200

    monkeypatch.setattr("app.api.server.requests.get", lambda *a, **k: _Resp())
    with TestClient(app) as c:
        resp = c.get("/health")
    assert resp.status_code == 200
    assert resp.json()["embedding_service"] == "ok"


def test_health_down(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*a: object, **k: object) -> object:
        raise requests.RequestException("unreachable")

    monkeypatch.setattr("app.api.server.requests.get", _boom)
    with TestClient(app) as c:
        resp = c.get("/health")
    assert resp.status_code == 503
    assert resp.json()["error"] == "embedding_service_down"
