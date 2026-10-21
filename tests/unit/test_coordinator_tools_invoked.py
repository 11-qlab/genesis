from __future__ import annotations

import json
from pathlib import Path

from agi.agents import Coordinator
from agi.core import load_config
from agi.providers.base import Completion, Message
from agi.storage import Store
from agi.tools import build_registry


class _Scripted:
    name = "s"
    model = "s-1"

    def __init__(self, payloads: list[dict]) -> None:
        self._queue = list(payloads)

    def complete(self, messages: list[Message], **_kw) -> Completion:
        if self._queue:
            head = self._queue.pop(0)
            return Completion(text=json.dumps(head), model=self.model)
        return Completion(text=json.dumps({"goal": "g", "steps": []}), model=self.model)

    def stream(self, messages: list[Message], **_kw):
        yield self.complete(messages).text

    def health(self) -> dict:
        return {"ok": True}


def test_tools_invoked_records_recovery(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    cfg = load_config()
    tools = build_registry(["fs_read", "fs_write"], str(ws))

    initial = {"goal": "g", "steps": [{
        "id": "s1", "title": "read",
        "tool": "fs_read", "args": {"path": "missing.txt"}, "depends_on": [],
    }]}
    recovery = {"goal": "r", "steps": [{
        "id": "r1", "title": "create",
        "tool": "fs_write",
        "args": {"path": "missing.txt", "content": "hi", "mode": "overwrite"},
        "depends_on": [],
    }]}

    provider = _Scripted([initial, recovery])
    store = Store(tmp_path / "s.sqlite3")
    try:
        coord = Coordinator(provider, tools, store, cfg.runtime)
        result = coord.execute("read the file")
        assert result["status"] == "succeeded"
        step = result["results"][0]
        assert step["ok"] is True
        assert step["attempts"] == 2
        assert step["tools_invoked"] == ["fs_read", "fs_write", "fs_read"]
    finally:
        store.close()
