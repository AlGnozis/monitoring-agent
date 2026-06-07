"""Build the FAISS knowledge-base index from markdown/text sources.

Loads `data/knowledge/*.{md,txt}`, light-cleans, chunks (512 chars / overlap 50),
embeds and saves a FAISS index to `kb_path`.

# Adapted from ai-factory backend modules/knowledge_base/vectorization.py
# Reason: reuse the chunking strategy (RecursiveCharacterTextSplitter 512/50) and the
# encoding-fallback loader. Trimmed to md/txt only (no PDF/DOCX) — not needed for the
# synthetic KB and avoids extra heavy deps.
"""

import re
from pathlib import Path

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import get_settings
from app.logger import log_info, log_warning
from app.rag.embeddings import E5RemoteEmbeddings

KNOWLEDGE_DIR = Path("data/knowledge")
_TEXT_SUFFIXES = {".md", ".txt"}
_ENCODINGS = ("utf-8-sig", "utf-8", "cp1251")


def _read_text(path: Path) -> str:
    for enc in _ENCODINGS:
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def _preprocess(text: str) -> str:
    text = re.sub(r" {2,}", " ", text)  # collapse runs of spaces
    text = re.sub(r"(\.\s*){3,}", ". ", text)  # collapse dot sequences
    return text


def load_documents(knowledge_dir: Path = KNOWLEDGE_DIR) -> list[Document]:
    docs: list[Document] = []
    for path in sorted(knowledge_dir.rglob("*")):
        if path.suffix.lower() not in _TEXT_SUFFIXES:
            continue
        text = _preprocess(_read_text(path))
        if text.strip():
            docs.append(Document(page_content=text, metadata={"source": path.name}))
    return docs


def build_index(
    *,
    knowledge_dir: Path = KNOWLEDGE_DIR,
    kb_path: Path | None = None,
    embeddings: Embeddings | None = None,
) -> int:
    """Build and persist the FAISS index; returns the number of chunks indexed."""
    kb_path = kb_path or get_settings().kb_path
    docs = load_documents(knowledge_dir)
    if not docs:
        log_warning(f"no documents found in {knowledge_dir}", "vectorize", "kb.empty", {"dir": str(knowledge_dir)})
        return 0

    splitter = RecursiveCharacterTextSplitter(chunk_size=512, chunk_overlap=50, separators=["\n\n", "\n", " ", ""])
    chunks = splitter.split_documents(docs)
    store = FAISS.from_documents(chunks, embeddings or E5RemoteEmbeddings())
    kb_path.mkdir(parents=True, exist_ok=True)
    store.save_local(str(kb_path))
    log_info(f"indexed {len(chunks)} chunks from {len(docs)} docs", "vectorize", "kb.built", {"chunks": len(chunks)})
    return len(chunks)
