"""Application settings (pydantic-settings).

Loaded from environment / `.env` (see `.env.example`). Single source of truth for
runtime configuration: GigaChat credentials, adapter/source selectors and paths.
Defaults keep the app importable without a `.env` (CI, unit tests).
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- GigaChat (passed as credentials+scope; the library refreshes the token, invariant #10) ---
    gigachat_auth_key: str = ""
    gigachat_scope: str = "GIGACHAT_API_PERS"

    # --- Selectors ---
    adapters: Literal["mock", "real"] = "mock"  # ticket/notify implementation (invariant #4)
    source: Literal["fake", "rss"] = "fake"  # event source; rss is deferred to iteration-2

    # --- Source / polling ---
    feed_url: str = ""  # required only when source == "rss"
    poll_interval_sec: int = 300

    # --- Embeddings / RAG ---
    embedding_service_url: str = "http://embedding-service:8000"
    kb_path: Path = Path("data/kb")  # FAISS index dir (gitignored, built by app.rag.build_kb)

    # --- Persistence (SQLite / files, gitignored) ---
    audit_db_path: Path = Path("audit.db")  # EventRecord audit store
    tickets_db_path: Path = Path("tickets.db")  # MockTicketAdapter store
    outbox_path: Path = Path("outbox")  # MockNotifyAdapter renders .eml here

    @property
    def embedding_endpoint(self) -> str:
        """Full URL the embeddings client POSTs to."""
        return f"{self.embedding_service_url.rstrip('/')}/embedding"

    @property
    def faiss_index_path(self) -> Path:
        """Path of the FAISS index file inside `kb_path`."""
        return self.kb_path / "index.faiss"

    @model_validator(mode="after")
    def _require_feed_url_for_rss(self) -> Self:
        if self.source == "rss" and not self.feed_url:
            raise ValueError("FEED_URL is required when SOURCE=rss")
        return self


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton for application code."""
    return Settings()
