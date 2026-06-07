"""Unit tests for app.config.Settings."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import Settings


def test_defaults() -> None:
    s = Settings(_env_file=None)
    assert s.adapters == "mock"
    assert s.source == "fake"
    assert s.poll_interval_sec == 300
    assert s.gigachat_scope == "GIGACHAT_API_PERS"
    assert s.embedding_service_url == "http://embedding-service:8000"
    assert s.kb_path == Path("data/kb")


def test_derived_properties() -> None:
    s = Settings(_env_file=None, embedding_service_url="http://host:8000/")
    assert s.embedding_endpoint == "http://host:8000/embedding"
    assert s.faiss_index_path == Path("data/kb/index.faiss")


def test_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADAPTERS", "real")
    monkeypatch.setenv("POLL_INTERVAL_SEC", "15")
    s = Settings(_env_file=None)
    assert s.adapters == "real"
    assert s.poll_interval_sec == 15


def test_invalid_adapter_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, adapters="bogus")  # type: ignore[arg-type]


def test_rss_requires_feed_url() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, source="rss", feed_url="")
    # with a url it is accepted
    s = Settings(_env_file=None, source="rss", feed_url="https://example.com/rss")
    assert s.feed_url == "https://example.com/rss"
