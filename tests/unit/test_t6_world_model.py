from __future__ import annotations

from agi.trajectories.t6_world_model import (
    GridWorld,
    TransitionModel,
    bfs,
    run_experiment,
)


def test_step_bounds() -> None:
    env = GridWorld(size=3)
    assert env.step((0, 0), "up") == (0, 0)
    assert env.step((0, 0), "down") == (0, 1)
    assert env.step((2, 2), "right") == (2, 2)
    assert env.step((2, 2), "up") == (2, 1)


def test_walls_block() -> None:
    env = GridWorld(size=3, walls={(1, 1)})
    assert env.step((0, 1), "right") == (0, 1)
    assert env.step((1, 0), "down") == (1, 0)


def test_bfs_trivial() -> None:
    env = GridWorld(size=3)
    assert bfs(env.step, (0, 0), (0, 0)) == []


def test_bfs_adjacent() -> None:
    env = GridWorld(size=3)
    path = bfs(env.step, (0, 0), (1, 0))
    assert path == ["right"]


def test_model_predicts_from_observation() -> None:
    model = TransitionModel()
    model.observe((0, 0), "right", (1, 0))
    model.observe((0, 0), "right", (1, 0))
    assert model.predict((0, 0), "right") == (1, 0)


def test_model_default_is_identity() -> None:
    model = TransitionModel()
    assert model.predict((5, 5), "up") == (5, 5)


def test_experiment_runs() -> None:
    result = run_experiment(n_episodes=5, n_observation_steps=100, size=3, seed=42)
    assert result["episodes"] >= 1
    assert 0.0 <= result["model_plan_rate"] <= 1.0
    assert 0.0 <= result["exact_match_rate"] <= 1.0
