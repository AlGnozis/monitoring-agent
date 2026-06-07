"""Unit tests for app.adapters (mock ticket/notify + factory)."""

from email import message_from_bytes
from email.policy import default as default_policy
from pathlib import Path

import pytest

from app.adapters.factory import get_notify_adapter, get_ticket_adapter
from app.adapters.notify import MockNotifyAdapter
from app.adapters.ticket import MockTicketAdapter
from app.config import Settings


def _ticket(tmp_path: Path) -> MockTicketAdapter:
    return MockTicketAdapter(db_path=tmp_path / "tickets.db")


def test_ticket_ids_are_sequential(tmp_path: Path) -> None:
    adapter = _ticket(tmp_path)
    assert adapter.create_ticket(event_hash="h1", summary="s1", severity="HIGH") == "DEMO-001"
    assert adapter.create_ticket(event_hash="h2", summary="s2", severity="LOW") == "DEMO-002"


def test_ticket_is_idempotent_by_event_hash(tmp_path: Path) -> None:
    adapter = _ticket(tmp_path)
    first = adapter.create_ticket(event_hash="same", summary="s", severity="HIGH")
    second = adapter.create_ticket(event_hash="same", summary="s-changed", severity="LOW")
    assert first == second == "DEMO-001"


def test_notify_writes_eml(tmp_path: Path) -> None:
    outbox = tmp_path / "outbox"
    adapter = MockNotifyAdapter(outbox_dir=outbox)
    adapter.send_notification(to="owner@bank", subject="Инцидент", body="детали", ref="demo-001")

    eml = outbox / "demo-001.eml"
    assert eml.exists()
    # policy.default -> EmailMessage with auto-decoded headers + get_content()
    msg = message_from_bytes(eml.read_bytes(), policy=default_policy)
    assert msg["To"] == "owner@bank"
    assert str(msg["Subject"]) == "Инцидент"
    assert "детали" in msg.get_content()


def test_notify_repeat_ref_keeps_single_file(tmp_path: Path) -> None:
    outbox = tmp_path / "outbox"
    adapter = MockNotifyAdapter(outbox_dir=outbox)
    adapter.send_notification(to="o@b", subject="s", body="b", ref="demo-001")
    adapter.send_notification(to="o@b", subject="s", body="b2", ref="demo-001")
    assert len(list(outbox.glob("*.eml"))) == 1


def test_factory_returns_mock_by_default(tmp_path: Path) -> None:
    s = Settings(
        _env_file=None,
        adapters="mock",
        tickets_db_path=tmp_path / "tickets.db",
        outbox_path=tmp_path / "outbox",
    )
    assert isinstance(get_ticket_adapter(s), MockTicketAdapter)
    assert isinstance(get_notify_adapter(s), MockNotifyAdapter)


def test_factory_real_not_implemented() -> None:
    s = Settings(_env_file=None, adapters="real")
    with pytest.raises(NotImplementedError):
        get_ticket_adapter(s)
    with pytest.raises(NotImplementedError):
        get_notify_adapter(s)
