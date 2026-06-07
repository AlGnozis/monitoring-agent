"""Unit tests for app.ingest.sources (FakeSource + factory)."""

import json
from pathlib import Path

from app.config import Settings
from app.ingest.sources import FakeSource, RssSource, get_source

_FEED = [
    {"entry_id": "demo-001", "title": "Платёжный шлюз", "body": "рост 5xx", "source": "fake"},
    {"entry_id": "demo-002", "title": "Релиз", "body": "тёмная тема", "source": "fake"},
]


def _feed_file(tmp_path: Path) -> Path:
    path = tmp_path / "fake_feed.json"
    path.write_text(json.dumps(_FEED, ensure_ascii=False), encoding="utf-8")
    return path


def test_fake_source_fetch(tmp_path: Path) -> None:
    src = FakeSource(feed_path=_feed_file(tmp_path))
    entries = src.fetch()
    assert [e.entry_id for e in entries] == ["demo-001", "demo-002"]
    assert entries[0].title == "Платёжный шлюз"


def test_fake_source_get(tmp_path: Path) -> None:
    src = FakeSource(feed_path=_feed_file(tmp_path))
    assert src.get("demo-002").title == "Релиз"  # type: ignore[union-attr]
    assert src.get("missing") is None


def test_get_source_factory(tmp_path: Path) -> None:
    fake_settings = Settings(_env_file=None, source="fake", fake_feed_path=_feed_file(tmp_path))
    assert isinstance(get_source(fake_settings), FakeSource)

    rss_settings = Settings(_env_file=None, source="rss", feed_url="https://example.com/rss")
    assert isinstance(get_source(rss_settings), RssSource)
