# T6 World Model — Learning Curve

**Measurement date:** 2026-10-20
**Code:** `src/agi/trajectories/t6_world_model.py::run_experiment`
**Environment:** 5×5 grid, 2 wall tiles (`(1,1)` and `(3,3)`), free positions
walkable. BFS with max_depth=12 in both true-environment and learned-model
planning.

## Protocol

For each observation count N:
- Run 40 episodes.
- Per episode: fresh random start/goal, N random transitions sampled from
  the true environment, learn a tabular transition model, plan with BFS
  on both the true env and the learned model.
- `model_plan_rate` = fraction of episodes where the learned-model BFS finds
  a path.
- `exact_match` = fraction of episodes where the learned-model path length
  matches the true-env path length.

Random seed 0. Episodes count 39 (one episode skipped because start==goal).
Fully offline; no API calls; no model involved. The "learning" is a count
histogram over (state, action) → next_state, argmax as the prediction.

## Result

| observations | episodes | model_plan_rate | exact_match |
| --- | --- | --- | --- |
| 50 | 39 | 0.359 | 0.205 |
| 100 | 39 | 0.615 | 0.462 |
| 250 | 39 | 0.923 | 0.897 |
| 500 | 39 | 1.000 | 1.000 |
| 1000 | 39 | 1.000 | 1.000 |
| 2000 | 39 | 1.000 | 1.000 |

## Honest interpretation

**What this is:** a learning curve for a *tabular* transition model on a
toy grid world. As N increases, the model's argmax converges to the true
transition function. At N≈500 on a 25-cell grid, the model's plan matches
the environment's plan in every episode of 40. At N≈250 it matches in
89.7%. At N≈50 it matches in only 20.5%.

**What this is NOT:**

- It is not a claim about deep world models. A pixel-input, learned-
  representation, continuous-dynamics world model (the kind that matters
  for Ha & Schmidhuber 2018 or LeCun's JEPA) is not present here.
- It is not a claim about data efficiency in general. Tabular models
  trivially saturate on tiny state spaces; that says nothing about how
  many observations a neural world model would need.
- It is not a claim about AGI.

**What it IS:**

A clean, honest demonstration that the trajectory "learn a world model,
plan on it" is buildable in this codebase and produces a monotonic
learning curve with a well-defined saturation point. It is the first
trajectory measurement in this project that required zero model calls
and produced a number that goes up with a knob you control.

## A prediction that was wrong

In the batch that generated this module, I estimated the learning curve
would show `model_plan_rate ≈ 1.0` at N=50. The actual number is 0.359.
The shape (monotonic increase) was right; the magnitude was wrong by
roughly an order of magnitude. Tabular models need more observations
than intuition suggests on small grids, because a 5×5 grid with two
walls has 23 free cells × 4 actions = 92 (state, action) pairs, and the
model must observe enough of them to disambiguate no-op moves from
blocked moves. That's the real cost.

If you want to improve the curve's steepness: fewer walls, larger
observation budget per state-action pair, or a prior on unobserved
transitions (e.g., assume no-op until proven otherwise, which this
module already does implicitly). Those are all follow-up experiments.
