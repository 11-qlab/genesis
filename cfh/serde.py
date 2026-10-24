"""Serialization: JSON <-> Trajectory."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

from .types import Step, StepKind, ToolCall, Trajectory


def step_to_dict(s: Step) -> dict[str, Any]:
    d: dict[str, Any] = {"kind": s.kind.value, "content": s.content, "step_index": s.step_index}
    if s.tool_call:
        d["tool_call"] = {"name": s.tool_call.name, "args": s.tool_call.args, "call_id": s.tool_call.call_id}
    if s.observation is not None:
        d["observation"] = s.observation
    if s.metadata:
        d["metadata"] = s.metadata
    return d


def trajectory_to_dict(t: Trajectory) -> dict[str, Any]:
    return {
        "goal": t.goal,
        "steps": [step_to_dict(s) for s in t.steps],
        "outcome": t.outcome,
        "traj_id": t.traj_id,
        "metadata": t.metadata,
    }


def step_from_dict(d: dict[str, Any]) -> Step:
    kind = StepKind(d.get("kind", "assistant"))
    tc = None
    if d.get("tool_call"):
        td = d["tool_call"]
        tc = ToolCall(name=td["name"], args=td.get("args", {}), call_id=td.get("call_id", ""))
    return Step(
        kind=kind,
        content=d.get("content", ""),
        tool_call=tc,
        observation=d.get("observation"),
        step_index=int(d.get("step_index", 0)),
        metadata=d.get("metadata", {}),
    )


def trajectory_from_dict(d: dict[str, Any]) -> Trajectory:
    return Trajectory(
        goal=d.get("goal", ""),
        steps=[step_from_dict(s) for s in d.get("steps", [])],
        outcome=d.get("outcome", "unknown"),
        traj_id=d.get("traj_id", ""),
        metadata=d.get("metadata", {}),
    )


def load_trajectory(path: str | Path) -> Trajectory:
    return trajectory_from_dict(json.loads(Path(path).read_text()))


def save_trajectory(t: Trajectory, path: str | Path) -> None:
    Path(path).write_text(json.dumps(trajectory_to_dict(t), indent=2))


def parse_genesis_log(raw: str, goal: str = "") -> Trajectory:
    steps: list[Step] = []
    idx = 0
    for line in raw.splitlines():
        line = line.rstrip()
        if not line.strip():
            continue
        if line.startswith(">") or line.startswith("<"):
            steps.append(Step(kind=StepKind.TOOL_RESULT, observation=line[1:].strip(), step_index=idx))
        elif "(" in line and line.endswith(")") and not line.startswith(" "):
            name, _, rest = line.partition("(")
            argstr = rest[:-1]
            try:
                args = json.loads(argstr)
            except json.JSONDecodeError:
                args = {"_raw": argstr}
            steps.append(Step(
                kind=StepKind.TOOL_CALL,
                tool_call=ToolCall(name=name.strip(), args=args, call_id=f"call_{idx}"),
                step_index=idx,
            ))
        else:
            steps.append(Step(kind=StepKind.ASSISTANT, content=line, step_index=idx))
        idx += 1
    return Trajectory(goal=goal, steps=steps)
