"""SURE-Act-style counterfactual branching."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from .types import Step, StepKind, ToolCall, Trajectory


Executor = Callable[[str, list[Step]], "ExecutionResult"]


@dataclass
class ExecutionResult:
    ok: bool
    observation: str
    state: dict[str, Any] = field(default_factory=dict)


@dataclass
class BranchPoint:
    step_index: int
    original: ToolCall
    alternatives: list[ToolCall] = field(default_factory=list)


@dataclass
class BranchResult:
    branch_point: BranchPoint
    action: ToolCall
    executed_ok: bool
    rollout_success: bool
    rollout_trace: list[Step]
    score: float


class CounterfactualEngine:
    def __init__(self, executor, roll_forward, max_rollout_steps=4):
        self.executor = executor
        self.roll_forward = roll_forward
        self.max_rollout_steps = max_rollout_steps

    def find_branch_points(self, traj, alt_fn=None):
        bps = []
        for i, tc in traj.iter_tool_calls():
            alts = alt_fn(tc) if alt_fn else self._default_alts(tc)
            if alts:
                bps.append(BranchPoint(step_index=i, original=tc, alternatives=alts))
        return bps

    def _default_alts(self, tc):
        out = []
        siblings = {
            "fs_read": "fs_write", "fs_write": "fs_read",
            "http_get": "http_post", "http_post": "http_get",
        }
        if tc.name in siblings:
            out.append(ToolCall(name=siblings[tc.name], args=dict(tc.args)))
        for k, v in list(tc.args.items())[:2]:
            if isinstance(v, str):
                out.append(ToolCall(name=tc.name, args={**tc.args, k: v + "_alt"}))
        return out

    def branch(self, goal, traj, bp):
        results = []
        actions = [bp.original] + bp.alternatives
        prefix = traj.steps[: bp.step_index]
        for act in actions:
            step = Step(kind=StepKind.TOOL_CALL, tool_call=act, step_index=bp.step_index)
            res = self.executor(goal, prefix + [step])
            obs_step = Step(kind=StepKind.TOOL_RESULT, observation=res.observation,
                            step_index=bp.step_index + 1)
            trace = prefix + [step, obs_step]
            success = self.roll_forward(goal, trace, self.max_rollout_steps)
            results.append(BranchResult(
                branch_point=bp, action=act, executed_ok=res.ok,
                rollout_success=success, rollout_trace=trace,
                score=1.0 if success else 0.0,
            ))
        return results
