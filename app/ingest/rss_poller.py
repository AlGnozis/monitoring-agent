"""Background feed poller: fetch source on an interval and hand off new entries.

Deferred in iteration-1 (not auto-started — § Anti-scope): the e2e path is driven by
POST /trigger. `run_once` is the pure, testable core (fetch + dedup); the thread loop
is a thin wrapper around it.

# Adapted from ai-factory backend modules/integrations/email_service_entrypoint.py
# Reason: reuse the daemon polling-loop pattern (threading.Event + per-id dedup).
"""

import threading
from collections.abc import Callable

from app.ingest.sources import Source
from app.logger import log_error, log_info
from app.state import FeedEntry

Handler = Callable[[FeedEntry], None]


class FeedPoller:
    def __init__(self, source: Source, handler: Handler, interval_sec: int = 300) -> None:
        self.source = source
        self.handler = handler
        self.interval_sec = interval_sec
        self._stop = threading.Event()
        self._seen: set[str] = set()

    def run_once(self) -> list[FeedEntry]:
        """Fetch and return only entries not seen before (dedup by entry_id)."""
        new = [entry for entry in self.source.fetch() if entry.entry_id not in self._seen]
        for entry in new:
            self._seen.add(entry.entry_id)
        return new

    def _loop(self) -> None:
        while not self._stop.is_set():
            for entry in self.run_once():
                try:
                    self.handler(entry)
                except Exception as exc:  # noqa: BLE001 - one bad entry must not kill the loop
                    log_error(f"handler failed for {entry.entry_id}: {exc}", "FeedPoller", "poll.error")
            self._stop.wait(self.interval_sec)

    def start(self) -> threading.Thread:
        thread = threading.Thread(target=self._loop, daemon=True, name="feed-poller")
        thread.start()
        log_info("feed poller started", "FeedPoller", "poll.started", {"interval": self.interval_sec})
        return thread

    def stop(self) -> None:
        self._stop.set()
