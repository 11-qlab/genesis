from __future__ import annotations

import json
from pathlib import Path

from agi.agents.conversation import Conversation
from agi.core import load_config
from agi.providers.base import Completion, Message
from agi.storage import Store
from agi.tools import build_registry


class _Scripted:
    name = "scripted"
    model = "scripted-1"

    def __init__(self, payloads: list) -> None:
        # each item is either a dict (plan) or a string (summary text)
        self._queue = list(payloads)
        self.calls: list[str] = []

    def complete(self, messages: list[Message], **_kw) -> Completion:
        # record whether this was the planner or the summarizer
        system = next((m.content for m in messages if m.role == "system"), "")
        is_summary = "summarizing" in system.lower()
        self.calls.append("summary" if is_summary else "plan")
        if not self._queue:
            text = "done"
        else:
            head = self._queue.pop(0)
            text = head if isinstance(head, str) else json.dumps(head)
        return Completion(text=text, model=self.model)

    def stream(self, messages: list[Message], **_kw):
        yield self.complete(messages).text

    def health(self) -> dict:
        return {"ok": True}


def _plan(goal: str, tool: str = "fs_list", args: dict | None = None) -> dict:
    return {
        "goal": goal,
        "steps": [{
            "id": "s1", "title": "t", "tool": tool,
            "args": args or {"path": "."}, "depends_on": [],
        }],
    }


def test_single_turn(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    cfg = load_config()
    provider = _Scripted([_plan("list files"), "I listed the workspace."])
    tools = build_registry(["fs_list"], str(ws))
    store = Store(tmp_path / "s.sqlite3")
    try:
        conv = Conversation(provider, tools, store, cfg.runtime)
        turn = conv.run_turn("list files")
        assert turn.status == "succeeded"
        assert turn.run_id is not None
        assert turn.tool_sequence == ("fs_list",)
        assert "listed" in turn.summary.lower()
        assert len(conv.history) == 1
        # call sequence: plan, summary
        assert provider.calls == ["plan", "summary"]
    finally:
        store.close()


def test_multi_turn_context(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    cfg = load_config()
    provider = _Scripted([
        _plan("first"), "first done",
        _plan("second"), "second done",
    ])
    tools = build_registry(["fs_list"], str(ws))
    store = Store(tmp_path / "s.sqlite3")
    try:
        conv = Conversation(provider, tools, store, cfg.runtime)
        t1 = conv.run_turn("first task")
        t2 = conv.run_turn("second task")
        assert t1.status == "succeeded"
        assert t2.status == "succeeded"
        # second turn's effective goal must reference the first
        assert "Recent conversation context" in t2.effective_goal
        assert "first task" in t2.effective_goal
        assert "Task: second task" in t2.effective_goal
        assert len(conv.history) == 2
    finally:
        store.close()


def test_max_turns_enforced(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    cfg = load_config()
    provider = _Scripted([_plan("x"), "ok", _plan("y"), "ok"])
    tools = build_registry(["fs_list"], str(ws))
    store = Store(tmp_path / "s.sqlite3")
    try:
        conv = Conversation(provider, tools, store, cfg.runtime, max_turns=1)
        conv.run_turn("first")
        try:
            conv.run_turn("second")
        except RuntimeError as exc:
            assert "max_turns" in str(exc)
        else:
            raise AssertionError("expected RuntimeError on max_turns")
    finally:
        store.close()


def test_clear(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    cfg = load_config()
    provider = _Scripted([_plan("x"), "ok"])
    tools = build_registry(["fs_list"], str(ws))
    store = Store(tmp_path / "s.sqlite3")
    try:
        conv = Conversation(provider, tools, store, cfg.runtime)
        conv.run_turn("first")
        assert len(conv.history) == 1
        conv.clear()
        assert conv.history == []
    finally:
        store.close()


def test_raw_summary_mode(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    cfg = load_config()
    provider = _Scripted([_plan("x")])
    tools = build_registry(["fs_list"], str(ws))
    store = Store(tmp_path / "s.sqlite3")
    try:
        conv = Conversation(provider, tools, store, cfg.runtime, summarize=False)
        turn = conv.run_turn("do it")
        # summarize=False means no second model call
        assert provider.calls == ["plan"]
        assert "1 step" in turn.summary
    finally:
        store.close()
