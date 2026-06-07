"""FAISS retriever returning a RagContext for the enrich_rag graph node.

Graceful degradation: if the index is missing, return an empty context
(`context_empty=True`) instead of raising — the plan node handles the gap.

# Adapted from ai-factory backend modules/knowledge_base entrypoint.py (/search)
# Reason: reuse similarity_search over a locally-saved FAISS index.
"""

from pathlib import Path

from langchain_community.vectorstores import FAISS
from langchain_core.embeddings import Embeddings

from app.config import get_settings
from app.rag.embeddings import E5RemoteEmbeddings
from app.state import RagContext


def _load_store(kb_path: Path, embeddings: Embeddings) -> FAISS | None:
    if not (kb_path / "index.faiss").exists():
        return None
    # allow_dangerous_deserialization: trusted only for OUR own artifact (invariant #7)
    return FAISS.load_local(str(kb_path), embeddings, allow_dangerous_deserialization=True)


def retrieve(
    query: str,
    *,
    k: int = 5,
    kb_path: Path | None = None,
    embeddings: Embeddings | None = None,
) -> RagContext:
    kb_path = kb_path or get_settings().kb_path
    store = _load_store(kb_path, embeddings or E5RemoteEmbeddings())
    if store is None:
        return RagContext(chunks=[], context_empty=True)
    results = store.similarity_search(query, k=k)
    chunks = [doc.page_content for doc in results]
    return RagContext(chunks=chunks, context_empty=not chunks)
