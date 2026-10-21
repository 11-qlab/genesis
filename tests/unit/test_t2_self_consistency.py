from __future__ import annotations

import json

from agi.providers.base import Completion, Message
from agi.trajectories import self_consistent_plan


class _Scripted:
    name = "s"
    model = "m"

    def __init__(self, payloads: list[dict]) -> None:
        self._queue = list(payloads)
        self.calls = 0

    def complete(self, messages: list[Message], **_kw) -> Completion:
        self.calls += 1
        head = self._queue.pop(0) if self._queue else {"goal": "g", "steps": []}
        return Completion(text=json.dumps(head), model=self.model)

    def stream(self, messages: list[Message], **_kw):
        yield self.complete(messages).text

    def health(self) -> dict:
        return {"ok": True}


def _plan(tool: str, args: dict) -> dict:
    return {"goal": "g", "steps": [
        {"id": "s1", "title": "t", "tool": tool, "args": args, "depends_on": []},
    ]}


def test_k1_degenerate():
    provider = _Scripted([_plan("fs_list", {"path": "."})])
    r = self_consistent_plan(provider, "g", [{"name": "fs_list"}], k=1)
    assert r.samples == 1
    assert r.valid_samples == 1
    assert r.agreement == 1.0


def test_majority_vote():
    """3 identical signatures, 2 different → majority is the 3-cluster."""
    a = _plan("fs_list", {"path": "."})
    b = _plan("fs_list", {"path": "."})
    c = _plan("fs_list", {"path": "."})
    d = _plan("fs_read", {"path": "x"})
    e = _plan("fs_read", {"path": "y"})
    provider = _Scripted([a, b, c, d, e])
    catalog = [{"name": "fs_list"}, {"name": "fs_read"}]
    r = self_consistent_plan(provider, "g", catalog, k=5)
    assert r.samples == 5
    assert r.valid_samples == 5
    assert r.clusters == 2
    assert r.majority_size == 3
    assert r.agreement == 0.6
    assert r.plan.steps[0].tool == "fs_list"


def test_all_invalid_raises():
    import pytest

    from agi.core.errors import PlanValidationError
    provider = _Scripted([{"bad": "plan"}] * 5)
    catalog = [{"name": "fs_list"}]
    with pytest.raises(PlanValidationError):
        self_consistent_plan(provider, "g", catalog, k=5)
