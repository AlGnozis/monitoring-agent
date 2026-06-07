"""Standalone E5 embedding service.

Matches the contract expected by app.rag.embeddings.E5RemoteEmbeddings:
POST /embedding {"texts": [...], "normalize": bool} -> {"embeddings": [[...]], "dimension": N}
GET  /health -> {"status": "ok"}

The client (E5RemoteEmbeddings) applies the `passage:` / `query:` prefixes; this
service embeds the given texts as-is.
"""

import os

from fastapi import FastAPI
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

MODEL_NAME = os.environ.get("MODEL_NAME", "intfloat/e5-small-v2")

app = FastAPI(title="embedding-service")
_model = SentenceTransformer(MODEL_NAME)


class EmbedRequest(BaseModel):
    texts: list[str]
    normalize: bool = True


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/embedding")
def embedding(req: EmbedRequest) -> dict[str, object]:
    vectors = _model.encode(req.texts, normalize_embeddings=req.normalize)
    return {"embeddings": vectors.tolist(), "dimension": int(vectors.shape[1])}
