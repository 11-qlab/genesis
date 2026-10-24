"""Core data model for trajectories and tool calls."""
from __future__ import annotations
import copy, hashlib, json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterator, Optional


class StepKind(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"


@dataclass
class ToolCall:
    name: str
    args: dict[str, Any]
    call_id: str = ""

    def short(self, max_len: int = 80) -> str:
        a = json.dumps(self.args, sort_keys=True)
        if len(a) > max_len:
            a = a[: max_len - 3] + "..."
        return f"{self.name}({a})"


@dataclass
class Step:
    kind: StepKind
    content: str = ""
    tool_call: Optional[ToolCall] = None
    observation: Optional[str] = None
    step_index: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def clone(self) -> "Step":
        tc = None
        if self.tool_call is not None:
            tc = ToolCall(
                name=self.tool_call.name,
                args=copy.deepcopy(self.tool_call.args),
                call_id=self.tool_call.call_id,
            )
        return Step(
            kind=self.kind,
            content=self.content,
            tool_call=tc,
            observation=self.observation,
            step_index=self.step_index,
            metadata=copy.deepcopy(self.metadata),
        )


@dataclass
class Trajectory:
    goal: str
    steps: list[Step]
    outcome: str = "unknown"
    traj_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.traj_id:
            self.traj_id = self.compute_id()

    def compute_id(self) -> str:
        h = hashlib.sha256()
        h.update(self.goal.encode())
        for s in self.steps:
            h.update(
                json.dumps(
                    {
                        "k": s.kind.value,
                        "c": s.content,
                        "tn": s.tool_call.name if s.tool_call else None,
                        "tc": s.tool_call.args if s.tool_call else None,
                        "o": s.observation,
                    },
                    sort_keys=True,
                ).encode()
            )
        return h.hexdigest()[:16]

    def clone(self) -> "Trajectory":
        return Trajectory(
            goal=self.goal,
            steps=[s.clone() for s in self.steps],
            outcome=self.outcome,
            traj_id="",
            metadata=dict(self.metadata),
        )

    def iter_tool_calls(self) -> Iterator[tuple[int, ToolCall]]:
        for i, s in enumerate(self.steps):
            if s.tool_call is not None:
                yield i, s.tool_call

    def tool_calls(self) -> list[ToolCall]:
        return [tc for _, tc in self.iter_tool_calls()]

    def signature(self) -> tuple[str, ...]:
        return tuple(
            s.tool_call.name if s.tool_call else f"<{s.kind.value}>"
            for s in self.steps
        )

    def num_tool_calls(self) -> int:
        return sum(1 for _ in self.iter_tool_calls())

    def to_messages(self) -> list[dict[str, Any]]:
        msgs: list[dict[str, Any]] = []
        for s in self.steps:
            if s.kind == StepKind.SYSTEM:
                msgs.append({"role": "system", "content": s.content})
            elif s.kind == StepKind.USER:
                msgs.append({"role": "user", "content": s.content})
            elif s.kind == StepKind.ASSISTANT:
                if s.tool_call is not None:
                    msgs.append({
                        "role": "assistant",
                        "content": s.content or "",
                        "tool_calls": [{
                            "id": s.tool_call.call_id or f"call_{s.step_index}",
                            "type": "function",
                            "function": {
                                "name": s.tool_call.name,
                                "arguments": json.dumps(s.tool_call.args),
                            },
                        }],
                    })
                else:
                    msgs.append({"role": "assistant", "content": s.content})
            elif s.kind == StepKind.TOOL_RESULT:
                msgs.append({
                    "role": "tool",
                    "tool_call_id": s.tool_call.call_id if s.tool_call else f"call_{s.step_index}",
                    "content": s.observation or "",
                })
        return msgs
