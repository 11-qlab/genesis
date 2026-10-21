from __future__ import annotations

import json
from pathlib import Path

from agi.core import load_config
from agi.providers.base import Completion, Message
from agi.storage import Store
from agi.tools import build_registry
from agi.trajectories.t13_revision import RevisionAgent


class _ContextAware:
    """Returns different plans depending on the prompt kind.

    - Initial plan: fails (reads a nonexistent file)
    - Recovery plan: empty (doesn't help)
    - Revision prompt (contains COMPLETELY REVISED): the behavior is
      controlled by `revision_works`
    """

    name = "scripted"
    model = "m"

    def __init__(self, revision_works: bool) -> None:
        self.revision_works = revision_works
        self.calls: list[str] = []

    def complete(self, messages: list[Message], **_kw) -> Completion:
        prompt = messages[-1].content if messages else ""
        self.calls.append(prompt)

        if "COMPLETELY REVISED" in prompt:
            plan = self._working_plan() if self.revision_works else self._failing_plan()
            return Completion(text=json.dumps(plan), model=self.model)
        if "Recovery for failed step" in prompt:
            return Completion(
                text=json.dumps({"goal": "r", "steps": []}), model=self.model,
            )
        return Completion(text=json.dumps(self._failing_plan()), model=self.model)

    def _failing_plan(self) -> dict:
        return {
            "goal": "g",
            "steps": [{
                "id": "s1", "title": "read missing",
                "tool": "fs_read", "args": {"path": "nope.txt"},
                "depends_on": [],
            }],
        }

    def _working_plan(self) -> dict:
        return {
            "goal": "g",
            "steps": [{
                "id": "s1", "title": "list",
                "tool": "fs_list", "args": {"path": "."},
                "depends_on": [],
            }],
        }

    def stream(self, messages: list[Message], **_kw):
        yield self.complete(messages).text

    def health(self) -> dict:
        return {"ok": True}


def test_success_on_first_plan(tmp_path: Path) -> None:
    """If the initial plan already succeeds, no revision is attempted."""

    class _AlwaysWorks:
        name = "ok"
        model = "m"

        def complete(self, messages: list[Message], **_kw) -> Completion:
            return Completion(
                text=json.dumps({
                    "goal": "g",
                    "steps": [{
                        "id": "s1", "title": "list",
                        "tool": "fs_list", "args": {"path": "."},
                        "depends_on": [],
                    }],
                }),
                model=self.model,
            )

        def stream(self, messages: list[Message], **_kw):
            yield self.complete(messages).text

        def health(self) -> dict:
            return {"ok": True}

    ws = tmp_path / "ws"
    ws.mkdir()
    cfg = load_config()
    tools = build_registry(["fs_list", "fs_read"], str(ws))
    store = Store(tmp_path / "s.sqlite3")
    try:
        agent = RevisionAgent(_AlwaysWorks(), tools, store, cfg.runtime)
        result = agent.execute("list")
        assert result.status == "succeeded"
        assert result.revisions_attempted == 0
        assert result.total_runs == 1
    finally:
        store.close()


def test_revision_recovers(tmp_path: Path) -> None:
    """First plan fails, revision succeeds → one revision, two runs."""
    ws = tmp_path / "ws"
    ws.mkdir()
    cfg = load_config()
    tools = build_registry(["fs_list", "fs_read"], str(ws))
    store = Store(tmp_path / "s.sqlite3")
    try:
        agent = RevisionAgent(
            _ContextAware(revision_works=True), tools, store, cfg.runtime,
            max_revisions=1,
        )
        result = agent.execute("do something")
        assert result.status == "succeeded"
        assert result.revisions_attempted == 1
        assert result.total_runs == 2
        # Verify the revision prompt was actually issued
        assert any("COMPLETELY REVISED" in c for c in agent.provider.calls)
    finally:
        store.close()


def test_revision_gives_up(tmp_path: Path) -> None:
    """Both plans fail → status failed after 1 revision attempt."""
    ws = tmp_path / "ws"
    ws.mkdir()
    cfg = load_config()
    tools = build_registry(["fs_list", "fs_read"], str(ws))
    store = Store(tmp_path / "s.sqlite3")
    try:
        agent = RevisionAgent(
            _ContextAware(revision_works=False), tools, store, cfg.runtime,
            max_revisions=1,
        )
        result = agent.execute("do something")
        assert result.status == "failed"
        assert result.revisions_attempted == 1
        assert result.total_runs == 2
    finally:
        store.close()


def test_max_revisions_zero_no_revision(tmp_path: Path) -> None:
    """max_revisions=0 → same as plain Coordinator (no revision)."""
    ws = tmp_path / "ws"
    ws.mkdir()
    cfg = load_config()
    tools = build_registry(["fs_list", "fs_read"], str(ws))
    store = Store(tmp_path / "s.sqlite3")
    try:
        agent = RevisionAgent(
            _ContextAware(revision_works=True), tools, store, cfg.runtime,
            max_revisions=0,
        )
        result = agent.execute("do something")
        assert result.status == "failed"
        assert result.revisions_attempted == 0
        assert result.total_runs == 1
    finally:
        store.close()
