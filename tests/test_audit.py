"""Unit tests for app.store.audit (SQLite audit + idempotency)."""

from pathlib import Path

from app.state import EventRecord, Status
from app.store.audit import AuditStore


def _store(tmp_path: Path) -> AuditStore:
    return AuditStore(db_path=tmp_path / "audit.db")


def test_unknown_event_is_not_processed(tmp_path: Path) -> None:
    store = _store(tmp_path)
    assert store.is_processed("missing") is False
    assert store.get("missing") is None


def test_pending_record_is_not_processed(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.save(EventRecord(event_hash="h1", status=Status.PENDING))
    assert store.is_processed("h1") is False


def test_done_record_is_processed(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.save(EventRecord(event_hash="h2", status=Status.DONE, ticket_id="DEMO-001"))
    assert store.is_processed("h2") is True
    rec = store.get("h2")
    assert rec is not None and rec.ticket_id == "DEMO-001"


def test_save_is_idempotent_upsert(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.save(EventRecord(event_hash="h3", status=Status.PENDING))
    store.save(EventRecord(event_hash="h3", status=Status.DONE))  # same PK -> update
    assert store.is_processed("h3") is True
    assert len(store.list_records()) == 1


def test_list_records(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.save(EventRecord(event_hash="a", status=Status.DONE))
    store.save(EventRecord(event_hash="b", status=Status.DROPPED))
    hashes = {r.event_hash for r in store.list_records()}
    assert hashes == {"a", "b"}
