"""Integrity checks for the shipped data fixtures (owners, feed, knowledge)."""

from pathlib import Path

from app.graph.owners import load_owners, make_owner_resolver
from app.ingest.sources import FakeSource
from app.rag.vectorize import load_documents

_DATA = Path("data")


def test_fake_feed_parses_into_entries() -> None:
    entries = FakeSource(feed_path=_DATA / "fake_feed.json").fetch()
    assert len(entries) >= 6
    ids = [e.entry_id for e in entries]
    assert len(ids) == len(set(ids))  # unique entry ids
    assert "demo-001" in ids


def test_owners_yaml_has_default_and_systems() -> None:
    owners = load_owners(_DATA / "owners.yaml")
    assert "default" in owners
    assert "payment-gateway" in owners
    resolve = make_owner_resolver(_DATA / "owners.yaml")
    assert "@" in resolve("payment-gateway").owner_email


def test_knowledge_base_has_documents() -> None:
    docs = load_documents(_DATA / "knowledge")
    assert len(docs) >= 4
    assert all(doc.page_content.strip() for doc in docs)
