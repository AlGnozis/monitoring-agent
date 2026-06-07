"""Unit tests for app.rag.vectorize + retriever, using deterministic fake embeddings.

No embedding-service / network: a hash-based FakeEmbeddings keeps FAISS happy offline.
"""

import hashlib
from pathlib import Path

from langchain_core.embeddings import Embeddings

from app.rag.retriever import retrieve
from app.rag.vectorize import build_index, load_documents


class FakeEmbeddings(Embeddings):
    dim = 32

    def _vec(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode()).digest()[: self.dim]
        return [b / 255 for b in digest]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vec(text)


def _seed_knowledge(kdir: Path) -> None:
    kdir.mkdir(parents=True)
    (kdir / "runbook.md").write_text("Платёжный шлюз: при росте 5xx рестартовать поды.", encoding="utf-8")
    (kdir / "past.md").write_text("Инцидент БД: replication lag, переключить на реплику.", encoding="utf-8")
    (kdir / "ignore.pdf").write_text("not indexed", encoding="utf-8")  # wrong suffix


def test_load_documents_filters_by_suffix(tmp_path: Path) -> None:
    kdir = tmp_path / "knowledge"
    _seed_knowledge(kdir)
    docs = load_documents(kdir)
    assert len(docs) == 2  # .pdf skipped
    assert {d.metadata["source"] for d in docs} == {"runbook.md", "past.md"}


def test_build_and_retrieve(tmp_path: Path) -> None:
    kdir = tmp_path / "knowledge"
    _seed_knowledge(kdir)
    kb = tmp_path / "kb"
    emb = FakeEmbeddings()

    n = build_index(knowledge_dir=kdir, kb_path=kb, embeddings=emb)
    assert n >= 2
    assert (kb / "index.faiss").exists()

    ctx = retrieve("платёжный шлюз ошибки", k=2, kb_path=kb, embeddings=emb)
    assert ctx.context_empty is False
    assert len(ctx.chunks) >= 1


def test_build_index_empty_dir_returns_zero(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    assert build_index(knowledge_dir=empty, kb_path=tmp_path / "kb", embeddings=FakeEmbeddings()) == 0


def test_retrieve_missing_index_is_graceful(tmp_path: Path) -> None:
    ctx = retrieve("anything", kb_path=tmp_path / "nope", embeddings=FakeEmbeddings())
    assert ctx.context_empty is True
    assert ctx.chunks == []
