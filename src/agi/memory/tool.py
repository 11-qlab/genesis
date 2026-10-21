"""Tool adapter: exposes Retriever as a ToolRegistry-compatible tool.

Lives under `memory/` rather than `tools/` so that `tools/` keeps its
dependency footprint (core + pydantic only). The CLI is the only place that
registers this into the registry.
"""

from __future__ import annotations

import json

from pydantic import BaseModel, Field

from ..tools.base import Tool, ToolResult
from .documents import MemoryError
from .retriever import Retriever


class _MemorySearchArgs(BaseModel):
    query: str = Field(min_length=1, description="Free-text search query.")
    k: int = Field(default=5, ge=1, le=20, description="Maximum hits to return.")


class MemorySearchTool(Tool):
    name = "memory_search"
    description = (
        "Search ingested documents (workspace notes, prior experiments) for "
        "chunks whose embeddings are closest to the query. Returns a JSON array "
        "of {document_id, chunk_index, score, text}."
    )
    args_model = _MemorySearchArgs

    def __init__(self, retriever: Retriever) -> None:
        self.retriever = retriever

    def run(self, query: str, k: int = 5) -> ToolResult:
        try:
            hits = self.retriever.search(query, k=k)
        except MemoryError as exc:
            return ToolResult(ok=False, output=str(exc), meta={"kind": "memory"})
        payload = [
            {
                "document_id": h.document_id,
                "chunk_index": h.chunk_index,
                "score": round(h.score, 6),
                "text": h.text,
            }
            for h in hits
        ]
        return ToolResult(
            ok=True,
            output=json.dumps(payload, ensure_ascii=False),
            meta={"count": len(payload), "kind": "memory"},
        )
