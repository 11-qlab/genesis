"""T6 — Toy world model.

T6 in the trajectory map is "learned world models" (Ha & Schmidhuber 2018;
LeCun's JEPA). Full versions train predictive models over pixel streams.

What is buildable here, without training, is the *conceptual* subset: a
discrete grid world with an explicit tabular transition model that is
learned from sampled trajectories. Two planning strategies are then
compared:

    plan_with_env(env, start, goal)  — BFS on the true transition function
    plan_with_model(model, start, goal)  — BFS on the learned transition function

The claim it can support:

    "On a toy grid world where the transition model is learned from N
     samples, does planning on the model find valid paths as often as
     planning on the true environment?"

The claim it cannot support:

    Anything about pixel-space world models, continuous dynamics,
    3D physics, or real robots. Those require a different architecture.

Keep the experiment small and honest.
"""

from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass, field
from typing import Any

# Actions are named so BFS order is deterministic
ACTIONS = ("up", "down", "left", "right")
Action = str
State = tuple[int, int]


@dataclass
class GridWorld:
    size: int
    walls: set[State] = field(default_factory=set)

    def step(self, state: State, action: Action) -> State:
        x, y = state
        if action == "up":
            candidate = (x, y - 1)
        elif action == "down":
            candidate = (x, y + 1)
        elif action == "left":
            candidate = (x - 1, y)
        elif action == "right":
            candidate = (x + 1, y)
        else:
            return state
        if not (0 <= candidate[0] < self.size and 0 <= candidate[1] < self.size):
            return state
        if candidate in self.walls:
            return state
        return candidate

    def random_state(self, rng: random.Random) -> State:
        free = [
            (x, y)
            for x in range(self.size)
            for y in range(self.size)
            if (x, y) not in self.walls
        ]
        return rng.choice(free)

    def all_states(self) -> list[State]:
        return [
            (x, y)
            for x in range(self.size)
            for y in range(self.size)
            if (x, y) not in self.walls
        ]


@dataclass
class TransitionModel:
    """Tabular learned model: (state, action) -> most_common_next_state."""

    counts: dict[tuple[State, Action], dict[State, int]] = field(default_factory=dict)

    def observe(self, state: State, action: Action, next_state: State) -> None:
        key = (state, action)
        self.counts.setdefault(key, {})
        self.counts[key][next_state] = self.counts[key].get(next_state, 0) + 1

    def predict(self, state: State, action: Action) -> State:
        key = (state, action)
        if key not in self.counts or not self.counts[key]:
            return state  # no observation: assume no-op
        # argmax by count, ties broken by tuple order for determinism
        return max(self.counts[key].items(), key=lambda kv: (kv[1], kv[0]))[0]


def collect_observations(
    env: GridWorld,
    *,
    n_steps: int,
    seed: int = 0,
) -> list[tuple[State, Action, State]]:
    rng = random.Random(seed)
    observations: list[tuple[State, Action, State]] = []
    state = env.random_state(rng)
    for _ in range(n_steps):
        action = rng.choice(ACTIONS)
        next_state = env.step(state, action)
        observations.append((state, action, next_state))
        state = next_state
    return observations


def learn_model(observations: list[tuple[State, Action, State]]) -> TransitionModel:
    model = TransitionModel()
    for s, a, ns in observations:
        model.observe(s, a, ns)
    return model


def bfs(
    step_fn,
    start: State,
    goal: State,
    *,
    max_depth: int = 20,
) -> list[Action] | None:
    if start == goal:
        return []
    visited: set[State] = {start}
    queue: deque[tuple[State, list[Action]]] = deque([(start, [])])
    while queue:
        state, path = queue.popleft()
        if len(path) >= max_depth:
            continue
        for action in ACTIONS:
            next_state = step_fn(state, action)
            if next_state in visited:
                continue
            new_path = [*path, action]
            if next_state == goal:
                return new_path
            visited.add(next_state)
            queue.append((next_state, new_path))
    return None


def plan_with_env(env: GridWorld, start: State, goal: State, max_depth: int = 20):
    return bfs(env.step, start, goal, max_depth=max_depth)


def plan_with_model(
    model: TransitionModel,
    start: State,
    goal: State,
    max_depth: int = 20,
):
    return bfs(model.predict, start, goal, max_depth=max_depth)


def run_experiment(
    *,
    n_episodes: int = 30,
    n_observation_steps: int = 500,
    size: int = 5,
    max_depth: int = 12,
    seed: int = 0,
) -> dict[str, Any]:
    """End-to-end toy world model experiment.

    For each episode:
      1. Fresh grid (fixed walls, fixed seed).
      2. Sample n_observation_steps random transitions.
      3. Learn a tabular transition model.
      4. Pick start and goal.
      5. Plan via BFS on true env; record path length.
      6. Plan via BFS on learned model; record path length.
      7. Report whether model path matches env path length.
    """
    env = GridWorld(size=size, walls={(1, 1), (3, 3)})
    rng = random.Random(seed)
    true_lengths: list[int] = []
    model_lengths: list[int | None] = []
    matches = 0
    for _ in range(n_episodes):
        start = env.random_state(rng)
        goal = env.random_state(rng)
        if start == goal:
            continue
        obs = collect_observations(env, n_steps=n_observation_steps, seed=rng.randint(0, 1 << 30))
        model = learn_model(obs)
        p_true = plan_with_env(env, start, goal, max_depth=max_depth)
        p_model = plan_with_model(model, start, goal, max_depth=max_depth)
        if p_true is None:
            continue
        true_lengths.append(len(p_true))
        model_lengths.append(None if p_model is None else len(p_model))
        if p_model is not None and len(p_model) == len(p_true):
            matches += 1
    n = len(true_lengths)
    model_plans = [x for x in model_lengths if x is not None]
    return {
        "episodes": n,
        "true_mean_path": (sum(true_lengths) / n) if n else 0.0,
        "model_plan_rate": (len(model_plans) / n) if n else 0.0,
        "exact_match_rate": (matches / n) if n else 0.0,
        "observation_steps_per_episode": n_observation_steps,
    }
