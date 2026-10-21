from __future__ import annotations

from pathlib import Path

from agi.memory import Document, HashEmbedding, Retriever
from agi.storage import Store


def test_ingest_and_search(tmp_path: Path) -> None:
    store = Store(tmp_path / "m.sqlite3")
    try:
        embedder = HashEmbedding(dim=256)
        retriever = Retriever(store, embedder, chunk_size=120, chunk_overlap=20)

        doc_a = Document.from_text(
            "a.txt", "the workspace contains many files about agents and tools"
        )
        doc_b = Document.from_text(
            "b.txt", "completely unrelated content about the weather in paris"
        )
        assert retriever.ingest_document(doc_a) > 0
        assert retriever.ingest_document(doc_b) > 0
        assert retriever.ingest_document(doc_a) == 0

        hits = retriever.search("workspace files agents", k=3)
        assert hits
        assert hits[0].document_id == doc_a.id, hits

        docs = retriever.list_documents()
        assert {d["id"] for d in docs} == {doc_a.id, doc_b.id}
    finally:
        store.close()
