"""Type-directed plan repair.

The algorithm:

    plan ← Planner(goal, catalog)
    errs ← typecheck(plan)
    while errs ≠ [] and attempt < max_attempts:
        plan ← Repair(goal, plan, errs, catalog)
        errs ← typecheck(plan)
    return plan if errs == [] else None

The Repair call sends the model a structured error report and asks for a
revised plan. This is different from the Coordinator's recovery loop in
two ways: (a) it runs *before* any tool executes, (b) the error format is
typed (arg name + expected type + got type), which is a stronger signal
than "step failed."
"""

from __future__ import annotations

import json

from ..providers.base import Message, Provider
from .planner import SYSTEM_PROMPT, extract_json_object
from .schemas import Plan
from .typecheck import TypeError, typecheck_plan

REPAIR_SYSTEM_PROMPT = (
    SYSTEM_PROMPT + "\n\n"
    "You are repairing a plan that failed static type checking. Use "
    "$step_id.field to reference a previous step's output "
    "(e.g. \"$s1.out\" for the text a previous step produced, "
    "\"$s1.ok\" for a boolean success flag). Do NOT invent other template "
    "syntax such as {{...}} or <%...%>; only $<id>.<field> is supported."
)


def _format_errors(errors: list[TypeError]) -> str:
    return "\n".join(f"  - step {e.step_id}: {e.message}" for e in errors)


def type_directed_repair(
    provider: Provider,
    goal: str,
    plan: Plan,
    *,
    catalog: list[dict],
    max_attempts: int = 2,
) -> Plan | None:
    errors = typecheck_plan(plan)
    attempt = 0
    while errors and attempt < max_attempts:
        attempt += 1
        messages = [
            Message(role="system", content=REPAIR_SYSTEM_PROMPT),
            Message(
                role="user",
                content=(
                    f"GOAL:\n{goal}\n\n"
                    f"PLAN (invalid):\n{json.dumps(plan.model_dump(), indent=2)}\n\n"
                    f"TYPE ERRORS:\n{_format_errors(errors)}\n\n"
                    f"AVAILABLE TOOLS:\n{json.dumps(catalog, indent=2)}\n\n"
                    "Return ONLY a corrected JSON plan now."
                ),
            ),
        ]
        completion = provider.complete(messages, temperature=0.0)
        try:
            new_plan = Plan.model_validate(extract_json_object(completion.text))
        except Exception:
            continue
        # An empty plan is not a fix. Rejecting it prevents the model from
        # "solving" a type error by deleting every step.
        if not new_plan.steps:
            continue
        plan = new_plan
        errors = typecheck_plan(plan)
    return plan if not errors else None
