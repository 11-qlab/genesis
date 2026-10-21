from __future__ import annotations

import json

from agi.providers import EchoProvider, Message


def test_complete_chat(echo: EchoProvider) -> None:
    r = echo.complete([Message(role="user", content="hi")])
    assert r.text == "echo: hi"
    assert r.finish_reason == "stop"
    assert r.usage.total_tokens > 0


def test_complete_plan_goal_extraction(echo: EchoProvider) -> None:
    prompt = "PLAN for goal: list files\nAvailable tools: fs_list"
    r = echo.complete([Message(role="system", content="planner"),
                       Message(role="user", content=prompt)])
    payload = json.loads(r.text)
    assert payload["goal"] == "list files"
    assert payload["steps"][0]["tool"] == "fs_list"


def test_stream(echo: EchoProvider) -> None:
    chunks = list(echo.stream([Message(role="user", content="a b c")]))
    joined = "".join(chunks)
    assert "a" in joined and "b" in joined and "c" in joined


def test_health(echo: EchoProvider) -> None:
    h = echo.health()
    assert h["ok"] is True
    assert h["provider"] == "echo"
