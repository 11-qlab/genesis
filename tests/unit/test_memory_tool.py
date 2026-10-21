from __future__ import annotations

import json
from pathlib import Path

from agi.memory import Document, HashEmbedding, MemorySearchTool, Retriever
from agi.storage import Store


def test_search_returns_json(tmp_path: Path) -> None:
    store = Store(tmp_path / "m.sqlite3")
    try:
        retriever = Retriever(store, HashEmbedding(dim=128))
        retriever.ingest_document(Document.from_text(
            "a.txt", "the workspace has files and agents and tools"
        ))
        tool = MemorySearchTool(retriever)
        result = tool.run(query="workspace files", k=3)
        assert result.ok
        payload = json.loads(result.output)
        assert payload and payload[0]["score"] > 0
        assert result.meta["count"] == len(payload)
    finally:
        store.close()


def test_search_empty_index_is_ok(tmp_path: Path) -> None:
    store = Store(tmp_path / "m.sqlite3")
    try:
        tool = MemorySearchTool(Retriever(store, HashEmbedding(dim=64)))
        result = tool.run(query="anything", k=3)
        assert result.ok
        assert json.loads(result.output) == []
    finally:
        store.close()


def test_search_invalid_args() -> None:
    """Args are validated by ToolRegistry.execute, not by run() itself.
    This test asserts the args_model rejects a too-large k."""
    import pydantic
    import pytest

    from agi.memory.tool import _MemorySearchArgs

    with pytest.raises(pydantic.ValidationError):
        _MemorySearchArgs(query="x", k=999)
