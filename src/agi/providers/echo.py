"""Deterministic offline provider used for tests and dry runs."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator

from .base import Completion, Message, Usage

_PLAN_TRIGGER = re.compile(r"\bPLAN\b|return only a json", re.IGNORECASE)
_GOAL_PATTERNS = (
    # Old planner prompt: "PLAN for goal: <goal>\n"
    re.compile(r"PLAN for goal:\s*(.+?)(?:\r?\n|$)", re.IGNORECASE),
    # New planner prompt: "GOAL:\n<goal>\n\nAVAILABLE TOOLS:"
    re.compile(r"^GOAL:\s*(.+?)(?:\r?\n|$)", re.IGNORECASE | re.MULTILINE),
)
_MEMORY_HINT = re.compile(r"\bsearch\b|\bmemory\b|\bretriev", re.IGNORECASE)


def _extract_goal(text: str) -> str:
    for pattern in _GOAL_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(1).strip()
    return text.strip() or "unnamed goal"


class EchoProvider:
    name = "echo"

    def __init__(self, model: str = "echo-1") -> None:
        self.model = model

    def _fs_list_plan(self, goal: str) -> str:
        return json.dumps({
            "goal": goal,
            "steps": [{
                "id": "s1",
                "title": "List workspace root",
                "tool": "fs_list",
                "args": {"path": "."},
                "depends_on": [],
            }],
        }, ensure_ascii=False)

    def _memory_search_plan(self, goal: str) -> str:
        return json.dumps({
            "goal": goal,
            "steps": [{
                "id": "s1",
                "title": "Search ingested documents",
                "tool": "memory_search",
                "args": {"query": goal, "k": 3},
                "depends_on": [],
            }],
        }, ensure_ascii=False)

    def complete(
        self,
        messages: list[Message],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> Completion:
        joined = "\n".join(m.content for m in messages)
        last_user = next((m.content for m in reversed(messages) if m.role == "user"), "")
        if _PLAN_TRIGGER.search(joined):
            goal = _extract_goal(last_user)
            if _MEMORY_HINT.search(goal):
                text = self._memory_search_plan(goal)
            else:
                text = self._fs_list_plan(goal)
        else:
            text = f"echo: {last_user}".strip()
        return Completion(
            text=text,
            model=self.model,
            usage=Usage(
                prompt_tokens=max(1, len(joined) // 4),
                completion_tokens=max(1, len(text) // 4),
            ),
            finish_reason="stop",
        )

    def stream(
        self,
        messages: list[Message],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> Iterator[str]:
        for chunk in self.complete(messages).text.split(" "):
            yield chunk + " "

    def health(self) -> dict:
        return {"ok": True, "provider": self.name, "model": self.model}
