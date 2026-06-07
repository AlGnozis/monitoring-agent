"""E5 embeddings client talking to the standalone embedding-service over HTTP.

Implements the langchain `Embeddings` interface. Applies the E5 prefixes
(invariant #9): `passage:` for documents, `query:` for queries — in one place.

# Adapted from ai-factory backend modules/knowledge_base/embeddings.py
# Reason: reuse the proven remote-E5 HTTP client (batching + prefixes); endpoint is
# our embedding-service (POST {url}/embedding -> {"embeddings": [...]}).
"""

import requests
from langchain_core.embeddings import Embeddings

from app.config import get_settings


class E5RemoteEmbeddings(Embeddings):
    def __init__(self, endpoint: str | None = None, *, batch_size: int = 32, timeout: int = 300) -> None:
        self.endpoint = endpoint or get_settings().embedding_endpoint
        self.batch_size = batch_size
        self.timeout = timeout

    def _embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            resp = requests.post(self.endpoint, json={"texts": batch, "normalize": True}, timeout=self.timeout)
            resp.raise_for_status()
            out.extend(resp.json()["embeddings"])
        return out

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed([f"passage: {t}" for t in texts])

    def embed_query(self, text: str) -> list[float]:
        return self._embed([f"query: {text}"])[0]
