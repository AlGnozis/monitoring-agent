"""Unit tests for app.ingest.rss_poller (pure dedup core, no threads)."""

from app.ingest.rss_poller import FeedPoller
from app.state import FeedEntry


class _StubSource:
    def __init__(self, entries: list[FeedEntry]) -> None:
        self.entries = entries

    def fetch(self) -> list[FeedEntry]:
        return self.entries

    def get(self, entry_id: str) -> FeedEntry | None:
        return next((e for e in self.entries if e.entry_id == entry_id), None)


def _entry(entry_id: str) -> FeedEntry:
    return FeedEntry(entry_id=entry_id, title="t", body="b", source="fake")


def test_run_once_dedups_across_calls() -> None:
    source = _StubSource([_entry("a"), _entry("b")])
    poller = FeedPoller(source, handler=lambda e: None)

    first = poller.run_once()
    assert {e.entry_id for e in first} == {"a", "b"}

    # nothing new on the second pass
    assert poller.run_once() == []

    # a freshly appeared entry is returned once
    source.entries.append(_entry("c"))
    assert {e.entry_id for e in poller.run_once()} == {"c"}
