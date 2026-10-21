from __future__ import annotations

import pytest

from agi.core.errors import PlanValidationError
from agi.providers.base import Completion, Message
from agi.reasoning import Planner, extract_json_object


def test_extract_fenced() -> None:
    text = '```json\n{"goal":"g","steps":[]}\n```'
    assert extract_json_object(text) == {"goal": "g", "steps": []}


def test_extract_bare() -> None:
    text = 'noise {"goal":"g","steps":[]} trailing'
    assert extract_json_object(text) == {"goal": "g", "steps": []}


def test_extract_none() -> None:
    with pytest.raises(PlanValidationError):
        extract_json_object("nothing here")


def test_planner_with_echo(echo) -> None:
    planner = Planner(echo, ["fs_list"])
    plan = planner.plan("list workspace")
    assert plan.goal == "list workspace"
    assert plan.steps and plan.steps[0].tool == "fs_list"


class _BadProvider:
    name = "bad"
    model = "bad-1"

    def complete(self, messages: list[Message], **_: object) -> Completion:
        return Completion(text="totally not json", model="bad-1")

    def stream(self, messages: list[Message], **_: object):  # pragma: no cover
        yield ""

    def health(self) -> dict:
        return {"ok": False, "provider": "bad"}


def test_planner_rejects_garbage() -> None:
    planner = Planner(_BadProvider(), ["fs_list"])
    with pytest.raises(PlanValidationError):
        planner.plan("anything")


class _BadToolProvider:
    name = "badtool"
    model = "badtool-1"

    def complete(self, messages: list[Message], **_: object) -> Completion:
        return Completion(
            text='{"goal":"g","steps":[{"id":"a","title":"A","tool":"ghost","args":{},"depends_on":[]}]}',
            model="badtool-1",
        )

    def stream(self, messages: list[Message], **_: object):  # pragma: no cover
        yield ""

    def health(self) -> dict:
        return {"ok": False}


def test_planner_rejects_unknown_tool() -> None:
    planner = Planner(_BadToolProvider(), ["fs_list"])
    with pytest.raises(PlanValidationError):
        planner.plan("anything")
