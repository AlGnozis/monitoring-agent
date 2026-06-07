"""CLI: rebuild the FAISS knowledge base from data/knowledge/.

Usage: python -m app.rag.build_kb
Requires the embedding-service to be reachable (EMBEDDING_SERVICE_URL).
"""

from app.config import get_settings
from app.logger import log_info
from app.rag.vectorize import build_index


def main() -> None:
    settings = get_settings()
    n = build_index(kb_path=settings.kb_path)
    log_info(f"KB build finished: {n} chunks at {settings.kb_path}", "build_kb", "kb.cli.done", {"chunks": n})


if __name__ == "__main__":
    main()
