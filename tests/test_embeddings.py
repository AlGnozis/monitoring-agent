"""Unit tests for app.rag.embeddings (E5 prefixes + HTTP payload), no network."""

from typing import Any

import pytest

import app.rag.embeddings as emb_mod
from app.rag.embeddings import E5RemoteEmbeddings


class _FakeResp:
    def __init__(self, embeddings: list[list[float]]) -> None:
        self._embeddings = embeddings

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict[str, Any]:
        return {"embeddings": self._embeddings}


def test_embed_documents_prefixes_passage(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_post(url: str, json: dict[str, Any], timeout: int) -> _FakeResp:
        captured["url"] = url
        captured["texts"] = json["texts"]
        return _FakeResp([[0.0] * 4 for _ in json["texts"]])

    monkeypatch.setattr(emb_mod.requests, "post", fake_post)
    e = E5RemoteEmbeddings(endpoint="http://x/embedding")
    vecs = e.embed_documents(["hello", "world"])

    assert captured["url"] == "http://x/embedding"
    assert captured["texts"] == ["passage: hello", "passage: world"]
    assert len(vecs) == 2


def test_embed_query_prefixes_query(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_post(url: str, json: dict[str, Any], timeout: int) -> _FakeResp:
        captured["texts"] = json["texts"]
        return _FakeResp([[0.1, 0.2]])

    monkeypatch.setattr(emb_mod.requests, "post", fake_post)
    e = E5RemoteEmbeddings(endpoint="http://x/embedding")
    vec = e.embed_query("hi")

    assert captured["texts"] == ["query: hi"]
    assert vec == [0.1, 0.2]
