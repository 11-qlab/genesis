"""End-to-end ingest + search over a SQLite-backed document store."""

from __future__ import annotations

import json
from pathlib import Path

try:
    import numpy as np
except ImportError:
    np = None  # type: ignore[assignment]

from ..storage.sqlite import Store
from .documents import Document, MemoryError, chunk_text
from .embeddings import EmbeddingProvider
from .index import FlatIndex, SearchHit


class Retriever:
    def __init__(
        self,
        store: Store,
        embedder: EmbeddingProvider,
        *,
        chunk_size: int = 400,
        chunk_overlap: int = 50,
    ) -> None:
        if np is None:
            raise MemoryError("numpy is required for Retriever")
        self.store = store
        self.embedder = embedder
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self._index: FlatIndex | None = None

    # --- ingest ---

    def ingest_document(self, doc: Document) -> int:
        existing = self.store.get_memory_document(doc.id)
        if existing is not None:
            return 0
        self.store.add_memory_document(
            doc_id=doc.id, source=doc.source, title=doc.title,
            text=doc.text, metadata=json.dumps(doc.metadata),
        )
        chunks = chunk_text(doc.text, size=self.chunk_size, overlap=self.chunk_overlap)
        if not chunks:
            return 0
        vectors = self.embedder.embed([c.text for c in chunks])
        for chunk, vec in zip(chunks, vectors, strict=True):
            self.store.add_memory_chunk(
                document_id=doc.id, idx=chunk.index, text=chunk.text,
                offset=chunk.offset, embedding=vec.tobytes(),
                embedding_dim=int(vec.shape[0]),
            )
        self._index = None  # invalidate cache
        return len(chunks)

    def ingest_file(self, path: str | Path) -> tuple[Document, int]:
        doc = Document.from_file(path)
        n = self.ingest_document(doc)
        return doc, n

    # --- search ---

    def _build_index(self) -> FlatIndex:
        if self._index is not None:
            return self._index
        index = FlatIndex()
        rows = self.store.list_memory_chunks()
        if not rows:
            self._index = index
            return index
        dims = {row["embedding_dim"] for row in rows}
        if len(dims) != 1:
            raise MemoryError(f"mixed embedding dims: {dims}")
        dim = dims.pop()
        matrix = np.zeros((len(rows), dim), dtype=np.float32)
        for i, row in enumerate(rows):
            matrix[i] = np.frombuffer(row["embedding"], dtype=np.float32)
        index.add(
            row_ids=[row["id"] for row in rows],
            document_ids=[row["document_id"] for row in rows],
            chunk_indexes=[row["idx"] for row in rows],
            texts=[row["text"] for row in rows],
            vectors=matrix,
        )
        self._index = index
        return index

    def search(self, query: str, *, k: int = 5) -> list[SearchHit]:
        if not query.strip():
            return []
        index = self._build_index()
        if len(index) == 0:
            return []
        q = self.embedder.embed([query])[0]
        return index.search(q, k=k)

    # --- listing ---

    def list_documents(self) -> list[dict]:
        return self.store.list_memory_documents()
