"""End-to-end: typed plans fix the class of failure that tc-09 showed."""

from __future__ import annotations

import json

from agi.agents import Coordinator
from agi.core import load_config
from agi.core.errors import PlanValidationError
from agi.providers.base import Completion
from agi.storage import Store
from agi.tools import build_registry


class _Scripted:
    name = "s"
    model = "s-1"

    def __init__(self, payloads):
        self._queue = list(payloads)
        self.calls = 0

    def complete(self, messages, **_kw):
        self.calls += 1
        head = self._queue.pop(0) if self._queue else {"goal": "g", "steps": []}
        return Completion(text=json.dumps(head), model=self.model)

    def stream(self, messages, **_kw):
        yield self.complete(messages).text

    def health(self):
        return {"ok": True}


def test_typed_coordinator_rejects_undefined_reference(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    cfg = load_config()
    tools = build_registry(["fs_list", "fs_read", "fs_write"], str(ws))

    bad = {
        "goal": "g",
        "steps": [{
            "id": "s1", "title": "read", "tool": "fs_read",
            "args": {"path": "$s2.out"},  # forward reference
            "depends_on": [],
        }],
    }
    provider = _Scripted([bad, bad])  # planner gives bad, repair also gives bad
    store = Store(tmp_path / "s.sqlite3")
    try:
        coord = Coordinator(
            provider, tools, store, cfg.runtime, enable_typed_plans=True,
        )
        try:
            coord.execute("read something")
        except PlanValidationError as exc:
            assert "type" in str(exc).lower()
        else:
            raise AssertionError("expected PlanValidationError")
    finally:
        store.close()


def test_typed_coordinator_fixes_forward_reference(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    cfg = load_config()
    tools = build_registry(["fs_list", "fs_write"], str(ws))

    bad = {
        "goal": "g",
        "steps": [{
            "id": "s2", "title": "write", "tool": "fs_write",
            "args": {"path": "out.txt", "content": "$s1.out",
                     "mode": "overwrite"},
            # No depends_on here: $s1.out alone expresses the data dependency.
            # Adding depends_on=["s1"] would fail graph validation in the
            # Planner before typecheck runs, which is a different failure mode.
            "depends_on": [],
        }],
    }
    good = {
        "goal": "g",
        "steps": [
            {"id": "s1", "title": "list", "tool": "fs_list",
             "args": {"path": "."}, "depends_on": []},
            {"id": "s2", "title": "write", "tool": "fs_write",
             "args": {"path": "out.txt", "content": "$s1.out",
                      "mode": "overwrite"},
             "depends_on": ["s1"]},
        ],
    }
    provider = _Scripted([bad, good])
    store = Store(tmp_path / "s.sqlite3")
    try:
        coord = Coordinator(
            provider, tools, store, cfg.runtime, enable_typed_plans=True,
        )
        result = coord.execute("list and write")
        assert result["status"] == "succeeded", result
        kinds = [e["kind"] for e in store.list_events(result["run_id"])]
        assert "plan.repaired" in kinds
    finally:
        store.close()
