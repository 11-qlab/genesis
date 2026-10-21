"""End-to-end conversation loop against the echo fixture (offline)."""

from __future__ import annotations

from pathlib import Path

from agi.agents.conversation import Conversation
from agi.core import load_config
from agi.providers import EchoProvider
from agi.storage import Store
from agi.tools import build_registry


def test_two_turns_with_echo(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    cfg = load_config()
    tools = build_registry(["fs_list"], str(ws))
    store = Store(tmp_path / "s.sqlite3")
    try:
        conv = Conversation(
            EchoProvider(), tools, store, cfg.runtime, summarize=False,
        )
        t1 = conv.run_turn("list everything")
        assert t1.status == "succeeded"
        assert t1.tool_sequence == ("fs_list",)
        t2 = conv.run_turn("list again")
        assert t2.status == "succeeded"
        assert "Recent conversation context" in t2.effective_goal
    finally:
        store.close()
