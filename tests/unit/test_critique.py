from __future__ import annotations

import json

from agi.providers.base import Completion, Message
from agi.reasoning.critique import PlanCritique
from agi.reasoning.schemas import Plan, PlanStep


class _Stub:
    name = "stub"
    model = "stub-1"

    def __init__(self, text: str) -> None:
        self._text = text
        self.last_user = ""

    def complete(self, messages: list[Message], **_kw) -> Completion:
        self.last_user = next(
            (m.content for m in reversed(messages) if m.role == "user"), ""
        )
        return Completion(text=self._text, model=self.model)

    def stream(self, messages: list[Message], **_kw):
        yield self.complete(messages).text

    def health(self) -> dict:
        return {"ok": True}


def _plan() -> Plan:
    return Plan(goal="g", steps=[
        PlanStep(id="s1", title="t", tool="fs_list", args={"path": "."}, depends_on=[]),
    ])


def test_critique_accept() -> None:
    stub = _Stub(json.dumps({"verdict": "accept", "reason": "looks fine"}))
    v = PlanCritique(stub).review("list files", _plan(), [{"name": "fs_list", "description": "list"}])
    assert v["verdict"] == "accept"
    assert v["reason"] == "looks fine"


def test_critique_reject() -> None:
    stub = _Stub('```json\n{"verdict": "reject", "reason": "wrong tool"}\n```')
    v = PlanCritique(stub).review("g", _plan(), [{"name": "fs_list", "description": "list"}])
    assert v["verdict"] == "reject"


def test_critique_unparsable() -> None:
    stub = _Stub("no json here at all")
    v = PlanCritique(stub).review("g", _plan(), [{"name": "fs_list", "description": "list"}])
    assert v["verdict"] == "unavailable"


def test_critique_bad_verdict_normalized() -> None:
    stub = _Stub(json.dumps({"verdict": "maybe", "reason": "?"}))
    v = PlanCritique(stub).review("g", _plan(), [{"name": "fs_list", "description": "list"}])
    assert v["verdict"] == "unavailable"
