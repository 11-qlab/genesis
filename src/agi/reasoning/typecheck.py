"""Static type checker for plans.

The theorem this file implements:

    Progress.    If Γ ⊢ P : Γ' and all tools in P are registered,
                 then either P is empty or P = s :: rest with
                 s.tool registered, s.id ∉ dom(Γ), and s.args
                 type-check in Γ.

    Preservation. If Γ ⊢ s :: rest : Γ' and s returns v:τ_s
                 matching the annotation, then Γ ⊎ {s.out:τ_s,
                 s.ok:Bool} ⊢ rest : Γ'.

    No-undefined-references (corollary). A well-typed plan cannot
                 fail at execution due to an unresolved $s.f ref.

See docs/research/TYPED_PLAN_CALCULUS.md.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .schemas import Plan
from .types import TOOL_SIGNATURES, T, TypeEnv

_REF = re.compile(r"^\$([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)$")


@dataclass(frozen=True)
class TypeError:
    """Not to be confused with Python's builtin TypeError."""

    step_id: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"step_id": self.step_id, "message": self.message}


def _literal_type(value: Any) -> T | None:
    if isinstance(value, bool):
        return T.BOOL
    if isinstance(value, int):
        return T.INT
    if isinstance(value, str):
        return T.STR
    return None


def _arg_type(env: TypeEnv, value: Any) -> tuple[T | None, str | None]:
    """Return (type, error_message). Exactly one of the two is not None."""
    if isinstance(value, str) and value.startswith("$"):
        match = _REF.match(value)
        if not match:
            return None, f"malformed reference {value!r} (expected $step_id.field)"
        step_id, field_name = match.group(1), match.group(2)
        resolved = env.lookup(step_id, field_name)
        if resolved is None:
            return None, (
                f"reference ${step_id}.{field_name} has no binding "
                f"(step must appear before this one and export the field)"
            )
        return resolved, None
    lit = _literal_type(value)
    if lit is None:
        return None, f"unsupported literal {value!r} (type {type(value).__name__})"
    return lit, None


def typecheck_plan(plan: Plan) -> list[TypeError]:
    """Return the list of type errors. Empty list means the plan is well-typed."""
    env = TypeEnv()
    errors: list[TypeError] = []
    for step in plan.steps:
        if step.tool is None:
            # No-op steps get Unit output, no args to check
            env = env.extend(step.id, T.UNIT)
            continue
        sig = TOOL_SIGNATURES.get(step.tool)
        if sig is None:
            errors.append(TypeError(step.id, f"unknown tool {step.tool!r}"))
            continue
        if env.lookup(step.id, "out") is not None:
            errors.append(TypeError(step.id, "duplicate step id"))
            continue
        if set(step.args.keys()) != set(sig.param_names()):
            errors.append(TypeError(
                step.id,
                f"args {sorted(step.args)} do not match params {list(sig.param_names())}",
            ))
            continue
        step_ok = True
        for param_name, expected_type in sig.params:
            arg_type, err = _arg_type(env, step.args[param_name])
            if err is not None:
                errors.append(TypeError(step.id, f"arg {param_name}: {err}"))
                step_ok = False
            elif arg_type != expected_type:
                errors.append(TypeError(
                    step.id,
                    f"arg {param_name}: type {arg_type.value} != expected "
                    f"{expected_type.value}",
                ))
                step_ok = False
        if step_ok:
            env = env.extend(step.id, sig.ret)
    return errors
