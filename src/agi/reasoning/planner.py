"""Model-driven planner with strict schema extraction."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from typing import Any

from ..core.errors import PlanValidationError
from ..providers.base import Message, Provider
from .schemas import Plan

_FENCED = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)

SYSTEM_PROMPT = (
    "You are the planner for an automated agent platform.\n"
    "Return ONLY a JSON object with this exact schema (no prose, no markdown fences):\n"
    '{"goal": str, "steps": [{"id": str, "title": str, '
    '"tool": str|null, "args": object, "depends_on": [str]}]}\n'
    "\n"
    "Rules:\n"
    "1. Step ids are unique and short (letters, digits, underscore).\n"
    "2. depends_on may only reference ids of steps defined earlier in the list.\n"
    "3. Every tool MUST appear in the provided tool list.\n"
    "4. Use the tool whose description best matches the goal. Read the "
    "descriptions carefully; do not assume every 'search' or 'list' means a "
    "filesystem operation.\n"
    "5. All `fs_*` paths are RELATIVE to the sandbox root. Never use "
    "absolute paths like '/' or '/notes'.\n"
    "6. Every tool has an args schema. Provide args that satisfy it exactly. "
    "For `fs_write`, `mode` accepts \"overwrite\" (default) or \"append\".\n"
    "7. When the goal uses a vague verb ('inspect', 'show', 'look at', 'what "
    "is', 'explore') and does not name a specific file, prefer `fs_list` over "
    "`fs_read`. Reading an assumed filename is a guess; listing is safe and "
    "informs the next step.\n"
    "8. The memory store is a separate domain from the filesystem. Goals that "
    "reference 'notes', 'docs', 'documents', 'memory', 'knowledge', or 'what I "
    "wrote' refer to the memory store and MUST use `memory_search`. Do not "
    "assume those words name files or directories on disk; they are not."
)


def _format_tool_catalog(tools: Iterable[dict[str, Any]]) -> str:
    lines: list[str] = []
    for tool in tools:
        name = tool.get("name", "?")
        desc = (tool.get("description") or "").strip().replace("\n", " ")
        args_schema = tool.get("args_schema") or {}
        props = args_schema.get("properties") or {}
        required = args_schema.get("required") or []
        args_bits: list[str] = []
        for arg_name, arg_schema in props.items():
            arg_type = arg_schema.get("type", "?")
            arg_desc = arg_schema.get("description", "")
            req_marker = " *required*" if arg_name in required else ""
            args_bits.append(f"    - {arg_name}: {arg_type}{req_marker} — {arg_desc}".rstrip(" —"))
        lines.append(f"- {name}: {desc}")
        if args_bits:
            lines.append("  args:")
            lines.extend(args_bits)
    return "\n".join(lines) if lines else "(no tools available)"


def extract_json_object(text: str) -> dict:
    for match in _FENCED.finditer(text):
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            continue

    start = text.find("{")
    while start != -1:
        depth = 0
        for index in range(start, len(text)):
            char = text[index]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : index + 1])
                    except json.JSONDecodeError:
                        break
        start = text.find("{", start + 1)

    raise PlanValidationError("no JSON object found in model output")


class Planner:
    def __init__(
        self,
        provider: Provider,
        tools: Iterable[str] | Iterable[dict[str, Any]],
    ) -> None:
        """`tools` accepts either names or richer dicts (name/description/args_schema).

        When dicts are passed, the descriptions and arg schemas go into the
        system prompt so the model can pick the right tool for the goal.
        """
        self.provider = provider
        items = list(tools)
        if not items:
            self.tool_names: list[str] = []
            self.tool_catalog: list[dict[str, Any]] = []
        elif isinstance(items[0], str):
            self.tool_names = sorted(str(x) for x in items)
            self.tool_catalog = [{"name": name} for name in self.tool_names]
        else:
            self.tool_catalog = list(items)  # type: ignore[arg-type]
            self.tool_names = sorted(t["name"] for t in self.tool_catalog)

    def plan(self, goal: str, temperature: float = 0.0) -> Plan:
        catalog_text = _format_tool_catalog(self.tool_catalog)
        messages = [
            Message(role="system", content=SYSTEM_PROMPT),
            Message(
                role="user",
                content=(
                    f"GOAL:\n{goal}\n\n"
                    f"AVAILABLE TOOLS:\n{catalog_text}\n\n"
                    "Produce a JSON plan now."
                ),
            ),
        ]
        completion = self.provider.complete(messages, temperature=temperature)
        payload = extract_json_object(completion.text)
        if (
            isinstance(payload, dict)
            and "steps" not in payload
            and ("tool" in payload or "title" in payload)
        ):
            payload = {"goal": goal, "steps": [payload]}
        # Wrap pydantic's ValidationError as PlanValidationError so callers
        # only ever handle one exception type from plan(). The message keeps
        # the field name so failure detail remains actionable.
        try:
            plan = Plan.model_validate(payload)
        except Exception as exc:
            raise PlanValidationError(
                f"plan schema validation failed: {exc}"
            ) from exc
        problems = plan.validate_graph(set(self.tool_names))
        if problems:
            raise PlanValidationError("; ".join(problems))
        return plan
