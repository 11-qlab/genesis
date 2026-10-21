from __future__ import annotations

import json

from agi.providers.base import Completion
from agi.reasoning import Plan, PlanStep, type_directed_repair, typecheck_plan


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


def _bad_plan():
    return Plan(goal="g", steps=[
        PlanStep(id="s1", title="t", tool="fs_read",
                 args={"path": "$s1.out"}),
    ])


def _fixed_plan():
    return {
        "goal": "g",
        "steps": [
            {"id": "s1", "title": "list", "tool": "fs_list",
             "args": {"path": "."}, "depends_on": []},
            {"id": "s2", "title": "write", "tool": "fs_write",
             "args": {"path": "a.txt", "content": "$s1.out",
                      "mode": "overwrite"},
             "depends_on": ["s1"]},
        ],
    }


def test_repair_succeeds():
    provider = _Scripted([_fixed_plan()])
    fixed = type_directed_repair(
        provider, "g", _bad_plan(), catalog=[], max_attempts=1,
    )
    assert fixed is not None
    assert typecheck_plan(fixed) == []
    assert provider.calls == 1


def test_repair_gives_up():
    provider = _Scripted([_bad_plan().model_dump() for _ in range(3)])
    fixed = type_directed_repair(
        provider, "g", _bad_plan(), catalog=[], max_attempts=2,
    )
    assert fixed is None
    assert provider.calls == 2
