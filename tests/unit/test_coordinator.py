from __future__ import annotations

import json
from pathlib import Path

import pytest

from agi.agents import Coordinator
from agi.core import load_config
from agi.core.errors import BudgetExceeded
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


def _plan(steps: list[dict], goal: str = "g") -> dict:
    return {"goal": goal, "steps": steps}


def test_recovery_succeeds(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    cfg = load_config()
    tools = build_registry(["fs_read", "fs_write"], str(ws))

    initial = _plan([{
        "id": "s1", "title": "read absent",
        "tool": "fs_read", "args": {"path": "absent.txt"}, "depends_on": [],
    }])
    recovery = _plan([{
        "id": "r1", "title": "create file",
        "tool": "fs_write",
        "args": {"path": "absent.txt", "content": "hi", "mode": "overwrite"},
        "depends_on": [],
    }], goal="recover")

    provider = _ScriptedProvider([initial, recovery])
    store = Store(tmp_path / "s.sqlite3")
    try:
        coord = Coordinator(provider, tools, store, cfg.runtime)
        result = coord.execute("read the file")
        assert result["status"] == "succeeded"
        assert result["results"][0]["ok"] is True
        assert result["results"][0]["attempts"] == 2
        kinds = [e["kind"] for e in store.list_events(result["run_id"])]
        assert "step.retry" in kinds and "step.recovery" in kinds
    finally:
        store.close()


def test_recovery_exhausted_marks_failed(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    cfg = load_config()
    tools = build_registry(["fs_read"], str(ws))

    initial = _plan([{
        "id": "s1", "title": "read absent",
        "tool": "fs_read", "args": {"path": "absent.txt"}, "depends_on": [],
    }])
    recovery = _plan([], goal="nothing we can do")

    provider = _ScriptedProvider([initial, recovery])
    store = Store(tmp_path / "s.sqlite3")
    try:
        coord = Coordinator(provider, tools, store, cfg.runtime)
        result = coord.execute("read the file")
        assert result["status"] == "failed"
        assert result["results"][0]["ok"] is False
        assert result["results"][0]["attempts"] == 2
        kinds = [e["kind"] for e in store.list_events(result["run_id"])]
        assert "step.failed" in kinds and "run.failed" in kinds
    finally:
        store.close()


def test_budget_exceeded_is_recorded(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    cfg = load_config()
    cfg.runtime.max_tool_calls = 1
    tools = build_registry(["fs_read"], str(ws))

    initial = _plan([{
        "id": "s1", "title": "read absent",
        "tool": "fs_read", "args": {"path": "absent.txt"}, "depends_on": [],
    }])
    recovery = _plan([{
        "id": "r1", "title": "empty recovery",
        "tool": "fs_read", "args": {"path": "absent.txt"}, "depends_on": [],
    }])

    provider = _ScriptedProvider([initial, recovery])
    store = Store(tmp_path / "s.sqlite3")
    try:
        coord = Coordinator(provider, tools, store, cfg.runtime)
        with pytest.raises(BudgetExceeded):
            coord.execute("read the file")
        runs = store.list_runs(5)
        assert runs and runs[0]["status"] == "failed"
    finally:
        store.close()


def test_no_reflection_when_retries_zero(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    cfg = load_config()
    tools = build_registry(["fs_read"], str(ws))

    initial = _plan([{
        "id": "s1", "title": "read absent",
        "tool": "fs_read", "args": {"path": "absent.txt"}, "depends_on": [],
    }])
    provider = _ScriptedProvider([initial])
    store = Store(tmp_path / "s.sqlite3")
    try:
        coord = Coordinator(provider, tools, store, cfg.runtime, max_step_retries=0)
        result = coord.execute("read the file")
        assert result["status"] == "failed"
        assert result["results"][0]["attempts"] == 1
        kinds = [e["kind"] for e in store.list_events(result["run_id"])]
        assert "step.retry" not in kinds
    finally:
        store.close()
