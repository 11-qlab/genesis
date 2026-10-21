"""Prove a Coordinator-driven plan can call memory_search through the
ToolRegistry, same path a real model would use."""

from __future__ import annotations

import json
from pathlib import Path

from agi.agents import Coordinator
from agi.core import load_config
from agi.memory import Document, HashEmbedding, MemorySearchTool, Retriever
from agi.providers.base import Completion, Message
from agi.storage import Store
from agi.tools import build_registry


class _ScriptedProvider:
    name = "scripted"
    model = "scripted-1"

    def __init__(self, payloads: list[dict]) -> None:
        self._payloads = [json.dumps(p) for p in payloads]
        self.calls = 0

    def complete(self, messages: list[Message], **_kw) -> Completion:
        idx = min(self.calls, len(self._payloads) - 1)
        self.calls += 1
        return Completion(text=self._payloads[idx], model=self.model)

    def stream(self, messages: list[Message], **_kw):
        yield self.complete(messages).text

    def health(self) -> dict:
        return {"ok": True, "provider": self.name}


def test_plan_calls_memory_search(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    cfg = load_config()
    store = Store(tmp_path / "s.sqlite3")
    try:
        retriever = Retriever(store, HashEmbedding(dim=128))
        retriever.ingest_document(Document.from_text(
            "notes.txt", "the filesystem tool is sandboxed to AGI_FS_ROOT"
        ))

        registry = build_registry(["fs_list"], str(ws))
        registry.register(MemorySearchTool(retriever))

        plan = {
            "goal": "search notes",
            "steps": [{
                "id": "s1", "title": "search memory",
                "tool": "memory_search",
                "args": {"query": "sandboxed filesystem", "k": 3},
                "depends_on": [],
            }],
        }
        provider = _ScriptedProvider([plan])
        coord = Coordinator(provider, registry, store, cfg.runtime)
        result = coord.execute("search notes")

        assert result["status"] == "succeeded", result
        step = result["results"][0]
        assert step["tool"] == "memory_search"
        assert step["ok"] is True
        hits = json.loads(step["output"])
        assert hits and hits[0]["score"] > 0
    finally:
        store.close()
