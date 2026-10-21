"""Post-plan self-critique.

After a plan is produced, an optional second model call asks: given this
goal and this plan, is the plan sound? The critique returns a verdict
in {"accept", "reject"} plus a one-sentence reason.

This is not a magic safety layer. It is a cheap external check that catches
the class of failures where the model picks a defensible-looking but wrong
tool. If the critique disagrees with the plan, the runner records the
disagreement; whether to block on it is a caller decision.
"""

from __future__ import annotations

import json
import re

from ..core.errors import PlanValidationError
from ..providers.base import Message, Provider
from .schemas import Plan

_CRITIQUE_PROMPT = (
    "You are a plan reviewer. Given a GOAL, a PLAN, and the TOOL CATALOG, "
    "decide whether the plan's tool choices and arguments are sound.\n"
    "Return ONLY this JSON:\n"
    '{"verdict": "accept" | "reject", "reason": str}\n'
    "Rules:\n"
    "- accept if each step's tool is the best fit for its sub-goal given the "
    "catalog, and its arguments are valid for that tool.\n"
    "- reject if any step uses the wrong tool for its sub-goal, or uses "
    "arguments that cannot be valid for that tool (e.g. absolute paths where "
    "a sandbox-relative path is required).\n"
    "- Do not invent tools not in the catalog."
)


def _format_catalog(tools: list[dict]) -> str:
    lines = []
    for tool in tools:
        name = tool.get("name", "?")
        desc = tool.get("description", "")
        lines.append(f"- {name}: {desc}")
    return "\n".join(lines) or "(no tools)"


def _parse_verdict(text: str) -> dict:
    # try fenced
    for match in re.finditer(r"```(?:json)?\s*(.*?)```", text, re.DOTALL):
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    # try first balanced object
    start = text.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : i + 1])
                    except json.JSONDecodeError:
                        break
        start = text.find("{", start + 1)
    raise PlanValidationError("critique returned no JSON")


class PlanCritique:
    def __init__(self, provider: Provider) -> None:
        self.provider = provider

    def review(
        self,
        goal: str,
        plan: Plan,
        tools: list[dict],
    ) -> dict:
        payload = {
            "goal": goal,
            "plan": plan.model_dump(),
            "tools": _format_catalog(tools),
        }
        messages = [
            Message(role="system", content=_CRITIQUE_PROMPT),
            Message(role="user", content=json.dumps(payload, indent=2)),
        ]
        completion = self.provider.complete(messages, temperature=0.0)
        try:
            verdict = _parse_verdict(completion.text)
        except PlanValidationError as exc:
            return {
                "verdict": "unavailable",
                "reason": f"could not parse critique output: {exc}",
            }
        verdict.setdefault("verdict", "unavailable")
        verdict.setdefault("reason", "")
        if verdict["verdict"] not in {"accept", "reject"}:
            verdict["verdict"] = "unavailable"
        return verdict
