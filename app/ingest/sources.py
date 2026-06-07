"""Event sources: deterministic FakeSource (default) and a live RssSource.

`FakeSource` reads `data/fake_feed.json` — reproducible for the demo and e2e tests.
`RssSource` (feedparser) exists as the live adapter but is deferred to iteration-2
(iteration-1 § Anti-scope). `get_source` selects by the `SOURCE` setting.
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

import feedparser

from app.config import Settings, get_settings
from app.state import FeedEntry


class Source(Protocol):
    def fetch(self) -> list[FeedEntry]:
        """Return all current entries from the source."""
        ...

    def get(self, entry_id: str) -> FeedEntry | None:
        """Return one entry by id, or None."""
        ...


class FakeSource:
    def __init__(self, feed_path: Path | None = None) -> None:
        self.feed_path = feed_path or get_settings().fake_feed_path

    def _load(self) -> list[FeedEntry]:
        data = json.loads(self.feed_path.read_text(encoding="utf-8"))
        return [FeedEntry(**item) for item in data]

    def fetch(self) -> list[FeedEntry]:
        return self._load()

    def get(self, entry_id: str) -> FeedEntry | None:
        return next((entry for entry in self._load() if entry.entry_id == entry_id), None)


class RssSource:
    def __init__(self, feed_url: str) -> None:
        self.feed_url = feed_url

    @staticmethod
    def _published(entry: Any) -> datetime | None:
        p = entry.get("published_parsed")
        if not p:
            return None
        return datetime(p[0], p[1], p[2], p[3], p[4], p[5], tzinfo=UTC)

    def fetch(self) -> list[FeedEntry]:
        parsed = feedparser.parse(self.feed_url)
        return [
            FeedEntry(
                entry_id=entry.get("id") or entry.get("link") or entry.get("title", ""),
                title=entry.get("title", ""),
                body=entry.get("summary", ""),
                source="rss",
                published_at=self._published(entry),
            )
            for entry in parsed.entries
        ]

    def get(self, entry_id: str) -> FeedEntry | None:
        return next((entry for entry in self.fetch() if entry.entry_id == entry_id), None)


def get_source(settings: Settings | None = None) -> Source:
    settings = settings or get_settings()
    if settings.source == "rss":
        return RssSource(settings.feed_url)
    return FakeSource(settings.fake_feed_path)
