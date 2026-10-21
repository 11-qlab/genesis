from __future__ import annotations

import json

from agi.providers.base import Completion, Message
from agi.reasoning import Planner
from agi.reasoning.schemas import Plan


class _BareStepProvider:
    name = "bare"
    model = "bare-1"

    def __init__(self, payload: dict) -> None:
        self._text = json.dumps(payload)

    def complete(self, messages: list[Message], **_kw) -> Completion:
        return Completion(text=self._text, model=self.model)

    def stream(self, messages: list[Message], **_kw):
        yield self.complete(messages).text

    def health(self) -> dict:
        return {"ok": True}


def test_bare_step_wrapped() -> None:
    step = {
        "id": "list_notes", "title": "list notes",
        "tool": "fs_list", "args": {"path": "."}, "depends_on": [],
    }
    provider = _BareStepProvider(step)
    plan = Planner(provider, ["fs_list"]).plan("list notes")
    assert isinstance(plan, Plan)
    assert plan.goal == "list notes"
    assert len(plan.steps) == 1
    assert plan.steps[0].id == "list_notes"
    assert plan.steps[0].tool == "fs_list"
