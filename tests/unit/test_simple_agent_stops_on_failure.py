"""Regression: SimpleAgent must stop when a step returns ok=False.

Before this fix, a failed tool execution (ok=False, not ToolError) was
recorded but the run continued and reported succeeded. See the 2026-10-20
T11 §1 diagnostic.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from agi.agents import SimpleAgent
from agi.core import load_config
from agi.core.errors import ToolError
from agi.providers.base import Completion, Message
from agi.storage import Store
from agi.tools import build_registry


class _Scripted:
    name = "s"
    model = "m"

    def complete(self, messages: list[Message], **_kw) -> Completion:
        return Completion(text=json.dumps({
            "goal": "g",
            "steps": [
                {"id": "s1", "title": "read missing",
                 "tool": "fs_read", "args": {"path": "absent.txt"},
                 "depends_on": []},
                {"id": "s2", "title": "list",
                 "tool": "fs_list", "args": {"path": "."},
                 "depends_on": ["s1"]},
            ],
        }), model=self.model)

    def stream(self, messages: list[Message], **_kw):
        yield self.complete(messages).text

    def health(self) -> dict:
        return {"ok": True}


def test_simple_agent_stops_on_failed_step(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    cfg = load_config()
    tools = build_registry(["fs_list", "fs_read"], str(ws))
    store = Store(tmp_path / "s.sqlite3")
    try:
        agent = SimpleAgent(_Scripted(), tools, store, cfg.runtime)
        with pytest.raises(ToolError) as exc:
            agent.execute("do the thing")
        assert "s1" in str(exc.value)
        runs = store.list_runs(5)
        assert runs
        assert runs[0]["status"] == "failed"
    finally:
        store.close()
