from __future__ import annotations

from pathlib import Path

from agi.agents import SimpleAgent
from agi.core import load_config
from agi.providers import EchoProvider
from agi.storage import Store
from agi.tools import build_registry


def test_agent_happy_path(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    cfg = load_config()
    provider = EchoProvider()
    tools = build_registry(["fs_list"], str(ws))
    store = Store(tmp_path / "s.sqlite3")
    try:
        agent = SimpleAgent(provider, tools, store, cfg.runtime)
        result = agent.execute("list everything")
        assert result["status"] == "succeeded"
        assert result["results"][0]["tool"] == "fs_list"
        kinds = [e["kind"] for e in store.list_events(result["run_id"])]
        assert kinds == [
            "run.started", "plan.created", "step.completed", "run.completed",
        ]
    finally:
        store.close()


def test_agent_tool_failure_marks_run_failed(tmp_path: Path) -> None:
    # Sandbox root intentionally absent -> fs_list returns ok=False.
    # SimpleAgent now aborts on ok=False (2026-10-20 fix).
    import pytest

    from agi.core.errors import ToolError
    cfg = load_config()
    provider = EchoProvider()
    tools = build_registry(["fs_list"], str(tmp_path / "does-not-exist"))
    store = Store(tmp_path / "s.sqlite3")
    try:
        agent = SimpleAgent(provider, tools, store, cfg.runtime)
        with pytest.raises(ToolError):
            agent.execute("list everything")
        runs = store.list_runs(5)
        assert runs
        assert runs[0]["status"] == "failed"
    finally:
        store.close()
