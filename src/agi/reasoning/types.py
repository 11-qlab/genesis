"""Type system for typed plan calculus.

See docs/research/TYPED_PLAN_CALCULUS.md for the formal development.
This module is the type checker's ground truth: it defines the types,
tool signatures, and the environment type.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class T(StrEnum):
    """Value types in a plan step's arguments."""

    UNIT = "Unit"
    STR = "Str"
    INT = "Int"
    BOOL = "Bool"


@dataclass(frozen=True)
class Signature:
    params: tuple[tuple[str, T], ...]
    ret: T

    def param_names(self) -> tuple[str, ...]:
        return tuple(name for name, _ in self.params)

    def param_types(self) -> dict[str, T]:
        return {name: typ for name, typ in self.params}


# Tool signatures. Kept in sync with the actual tool implementations.
# If a signature here is wrong, the type checker will be wrong.
TOOL_SIGNATURES: dict[str, Signature] = {
    "fs_list": Signature((("path", T.STR),), T.STR),
    "fs_read": Signature((("path", T.STR),), T.STR),
    "fs_write": Signature(
        (("path", T.STR), ("content", T.STR), ("mode", T.STR)), T.UNIT,
    ),
    "memory_search": Signature((("query", T.STR), ("k", T.INT)), T.STR),
    "shell": Signature((("command", T.STR), ("timeout_s", T.INT)), T.STR),
}


@dataclass
class TypeEnv:
    """Environment: map from (step_id, field_name) to type."""

    bindings: dict[tuple[str, str], T] = field(default_factory=dict)

    def extend(self, step_id: str, out_type: T) -> TypeEnv:
        new = dict(self.bindings)
        new[(step_id, "out")] = out_type
        new[(step_id, "ok")] = T.BOOL
        return TypeEnv(new)

    def lookup(self, step_id: str, field_name: str) -> T | None:
        return self.bindings.get((step_id, field_name))
