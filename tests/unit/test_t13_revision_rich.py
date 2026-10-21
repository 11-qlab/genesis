from __future__ import annotations

import json
from pathlib import Path

import pytest

from agi.core import load_config
from agi.providers.base import Completion, Message
from agi.storage import Store
from agi.tools import build_registry
from agi.trajectories.t13_revision import RevisionAgent


class _Ctx:
    name = "ctx"
    model = "m"

    def __init__(self, rich_fixes: bool) -> None:
        self.rich_fixes = rich_fixes
        self.calls: list[str] = []

    def complete(self, messages: list[Message], **_kw) -> Completion:
        prompt = messages[-1].content if messages else ""
        self.calls.append(prompt)
        if "REVISED ATTEMPT" in prompt:
            if self.rich_fixes:
                return Completion(
                    text=json.dumps({
                        "goal": "g",
                        "steps": [{
                            "id": "s1", "title": "list",
                            "tool": "fs_list",
                            "args": {"path": "."}, "depends_on": [],
                        }],
                    }),
                    model=self.model,
                )
            return Completion(
                text=json.dumps({
                    "goal": "g",
                    "steps": [{
                        "id": "s1", "title": "read missing",
                        "tool": "fs_read",
                        "args": {"path": "nope.txt"}, "depends_on": [],
                    }],
                }),
                model=self.model,
            )
        if "Recovery for failed step" in prompt:
            return Completion(
                text=json.dumps({"goal": "r", "steps": []}), model=self.model,
            )
        return Completion(
            text=json.dumps({
                "goal": "g",
                "steps": [{
                    "id": "s1", "title": "read missing",
                    "tool": "fs_read",
                    "args": {"path": "nope.txt"}, "depends_on": [],
                }],
            }),
            model=self.model,
        )

    def stream(self, messages: list[Message], **_kw):
        yield self.complete(messages).text

    def health(self) -> dict:
        return {"ok": True}


def test_signal_rejects_unknown(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    cfg = load_config()
    tools = build_registry(["fs_list"], str(ws))
    store = Store(tmp_path / "s.sqlite3")
    try:
        with pytest.raises(ValueError):
            RevisionAgent(
                _Ctx(True), tools, store, cfg.runtime, signal="weird",
            )
    finally:
        store.close()


def test_rich_prompt_contains_walk_and_hint(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    cfg = load_config()
    tools = build_registry(["fs_list", "fs_read"], str(ws))
    store = Store(tmp_path / "s.sqlite3")
    try:
        provider = _Ctx(rich_fixes=True)
        agent = RevisionAgent(
            provider, tools, store, cfg.runtime,
            max_revisions=1, signal="rich",
        )
        result = agent.execute("do something")
        rich_calls = [c for c in provider.calls if "REVISED ATTEMPT" in c]
        assert rich_calls, "no rich revision prompt issued"
        prompt = rich_calls[0]
        assert "Full plan and outcomes" in prompt
        assert "classification:" in prompt
        assert result.status == "succeeded"
        assert result.revisions_attempted == 1
    finally:
        store.close()


def test_rich_gives_up(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    cfg = load_config()
    tools = build_registry(["fs_list", "fs_read"], str(ws))
    store = Store(tmp_path / "s.sqlite3")
    try:
        agent = RevisionAgent(
            _Ctx(rich_fixes=False), tools, store, cfg.runtime,
            max_revisions=1, signal="rich",
        )
        result = agent.execute("do something")
        assert result.status == "failed"
        assert result.revisions_attempted == 1
    finally:
        store.close()


def test_basic_mode_uses_short_prompt(tmp_path: Path) -> None:
    """Signal=basic uses the short prompt, not rich."""
    ws = tmp_path / "ws"
    ws.mkdir()
    cfg = load_config()
    tools = build_registry(["fs_list", "fs_read"], str(ws))
    store = Store(tmp_path / "s.sqlite3")
    try:
        provider = _Ctx(rich_fixes=True)
        agent = RevisionAgent(
            provider, tools, store, cfg.runtime,
            max_revisions=1, signal="basic",
        )
        agent.execute("do something")
        rich_calls = [c for c in provider.calls if "REVISED ATTEMPT" in c]
        short_calls = [
            c for c in provider.calls if "COMPLETELY REVISED" in c
            and "REVISED ATTEMPT" not in c
        ]
        assert not rich_calls
        assert short_calls
    finally:
        store.close()
