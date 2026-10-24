"""Mutation operators. Each is a deterministic, seedable transform."""
from __future__ import annotations
import random
from abc import ABC, abstractmethod
from typing import Any, Callable, Optional

from .types import Step, StepKind, ToolCall, Trajectory


class Mutation(ABC):
    name: str = "mutation"

    @abstractmethod
    def apply(self, traj: Trajectory, rng: random.Random) -> Optional[Trajectory]:
        """Return a mutated clone, or None if the mutation is inapplicable."""


class SwapArgumentMutation(Mutation):
    name = "swap_argument"

    def __init__(self, neighbor_fn: Optional[Callable[[str, Any], Any]] = None, prob: float = 1.0):
        self.neighbor_fn = neighbor_fn
        self.prob = prob

    def _mutate_value(self, key: str, value: Any, rng: random.Random) -> Any:
        if self.neighbor_fn is not None:
            nv = self.neighbor_fn(key, value)
            if nv is not None:
                return nv
        if isinstance(value, str):
            if "/" in value:
                parts = value.rsplit("/", 1)
                return parts[0] + "/" + parts[1] + "_v2"
            return value + "_alt"
        if isinstance(value, bool):
            return not value
        if isinstance(value, int):
            return value + rng.choice([-1, 1])
        if isinstance(value, float):
            return value * rng.choice([0.5, 1.5, 2.0])
        if isinstance(value, list) and value:
            i = rng.randrange(len(value))
            new = list(value)
            new[i] = self._mutate_value(key, new[i], rng)
            return new
        if isinstance(value, dict) and value:
            k = rng.choice(list(value.keys()))
            new = dict(value)
            new[k] = self._mutate_value(k, new[k], rng)
            return new
        return value

    def apply(self, traj: Trajectory, rng: random.Random) -> Optional[Trajectory]:
        calls = list(traj.iter_tool_calls())
        if not calls:
            return None
        idx, tc = rng.choice(calls)
        if not tc.args:
            return None
        key = rng.choice(list(tc.args.keys()))
        new = traj.clone()
        new.steps[idx].tool_call.args[key] = self._mutate_value(key, tc.args[key], rng)
        return new


class SwapToolMutation(Mutation):
    name = "swap_tool"

    DEFAULT_MAP = {
        "fs_read": "fs_write", "fs_write": "fs_read", "fs_list": "fs_read",
        "http_get": "http_post", "http_post": "http_get",
        "sql_query": "sql_exec", "search": "grep", "grep": "search",
    }

    def __init__(self, swap_map: Optional[dict[str, str]] = None):
        self.swap_map = dict(swap_map or self.DEFAULT_MAP)

    def apply(self, traj: Trajectory, rng: random.Random) -> Optional[Trajectory]:
        calls = [(i, tc) for i, tc in traj.iter_tool_calls() if tc.name in self.swap_map]
        if not calls:
            return None
        idx, tc = rng.choice(calls)
        new = traj.clone()
        new.steps[idx].tool_call.name = self.swap_map[tc.name]
        return new


class StaleObservationMutation(Mutation):
    name = "stale_observation"

    def apply(self, traj: Trajectory, rng: random.Random) -> Optional[Trajectory]:
        obs_idx = [i for i, s in enumerate(traj.steps) if s.observation is not None]
        if len(obs_idx) < 2:
            return None
        target = rng.choice(obs_idx[1:])
        earlier = [i for i in obs_idx if i < target]
        if not earlier:
            return None
        src = rng.choice(earlier)
        new = traj.clone()
        new.steps[target].observation = new.steps[src].observation
        return new


class TruncateMutation(Mutation):
    name = "truncate"

    def apply(self, traj: Trajectory, rng: random.Random) -> Optional[Trajectory]:
        calls = list(traj.iter_tool_calls())
        if len(calls) < 2:
            return None
        idx, _ = rng.choice(calls)
        new = traj.clone()
        drop = {idx}
        if idx + 1 < len(new.steps) and new.steps[idx + 1].kind == StepKind.TOOL_RESULT:
            drop.add(idx + 1)
        new.steps = [s for i, s in enumerate(new.steps) if i not in drop]
        return new


class ReorderMutation(Mutation):
    name = "reorder"

    def apply(self, traj: Trajectory, rng: random.Random) -> Optional[Trajectory]:
        calls = [i for i, _ in traj.iter_tool_calls()]
        if len(calls) < 2:
            return None
        i = rng.choice(calls[:-1])
        if i + 1 not in calls:
            return None
        new = traj.clone()
        new.steps[i], new.steps[i + 1] = new.steps[i + 1], new.steps[i]
        return new


class HallucinateFieldMutation(Mutation):
    name = "hallucinate_field"
    CANDIDATE_FIELDS = ("encoding", "timeout_ms", "retries", "follow_symlinks", "force")

    def apply(self, traj: Trajectory, rng: random.Random) -> Optional[Trajectory]:
        calls = list(traj.iter_tool_calls())
        if not calls:
            return None
        idx, tc = rng.choice(calls)
        new = traj.clone()
        field = rng.choice(self.CANDIDATE_FIELDS)
        if field in tc.args:
            return None
        new.steps[idx].tool_call.args[field] = rng.choice([True, 1, "utf-8"])
        return new


class ShortcutTwinMutation(Mutation):
    """THE KEY MUTATION.

    Replace a tool call + its observation with an inferred assertion — the
    model writes down what it *believes* the tool would return, without calling
    it. This is exactly the hull behavior (`fs_read` skipped, `fs_write` written
    from inference) that T11 identified.
    """
    name = "shortcut_twin"

    def __init__(self, infer_fn: Optional[Callable[[str, list[Step], ToolCall], str]] = None):
        self.infer_fn = infer_fn

    def apply(self, traj: Trajectory, rng: random.Random) -> Optional[Trajectory]:
        calls = list(traj.iter_tool_calls())
        if not calls:
            return None
        idx, tc = rng.choice(calls)
        new = traj.clone()
        if self.infer_fn is not None:
            prefix = new.steps[:idx]
            inferred = self.infer_fn(traj.goal, prefix, tc)
        else:
            inferred = f"(inferred) {tc.name} would return a successful result"
        new.steps[idx] = Step(
            kind=StepKind.ASSISTANT,
            content=f"I already know the result of {tc.short()}: {inferred}",
            step_index=idx,
        )
        if idx + 1 < len(new.steps) and new.steps[idx + 1].kind == StepKind.TOOL_RESULT:
            new.steps.pop(idx + 1)
        return new


DEFAULT_MUTATIONS: list[Mutation] = [
    SwapArgumentMutation(),
    SwapToolMutation(),
    StaleObservationMutation(),
    HallucinateFieldMutation(),
    ReorderMutation(),
]
