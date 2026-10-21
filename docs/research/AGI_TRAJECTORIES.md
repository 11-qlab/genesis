# AGI Trajectories — the honest map

Ten research trajectories that the field considers plausible contributors
to AGI. Each entry states: canonical work, status in this repo, whether
it is buildable here, and what it would measure if built.

**This document is a map, not a promise.** No trajectory alone leads to
AGI. Combinations are speculative. The current project builds 4 of the
10 measurable pieces; the other 6 require hardware, training compute, or
sensorimotor grounding that this codebase cannot provide.

## T1 — Scaling

Canonical: Kaplan et al. 2020 (scaling laws for neural LMs); Hoffmann
et al. 2022 (Chinchilla).

Status: nothing in this repo. Requires training 100M–100B param models,
which requires GPUs, datasets, and weeks of wall time.

Buildable here: no. Compute is the limit, not code.

What it would test: whether a larger model on more data produces
qualitative jumps in capability, not just smoother curves.

## T2 — Prompted reasoning

Canonical: Wei et al. 2022 (chain-of-thought); Wang et al. 2022
(self-consistency, majority vote over k samples); Yao et al. 2023
(tree-of-thought).

Status in this repo: **building now** (`src/agi/trajectories/t2_reasoning.py`).

Buildable here: yes. Measures: does sampling k plans at temperature > 0
and taking the majority (by step signature) improve accuracy over a
single greedy sample, on the same benchmark, with the same model?

## T3 — Tool-using agents

Canonical: Yao et al. 2022 (ReAct); Schick et al. 2023 (Toolformer).

Status: **built.** `Coordinator` with tool registry, plan→execute→record.
This is the class of trajectory this project's shell *is*.

Buildable here: yes — it is the current project.

What it measures: how reliably a model selects and calls tools given a
catalog and a goal.

## T4 — Embodied grounding

Canonical: Baker et al. 2019 (Hide and Seek); Duan et al. 2022 (MineDojo).

Status: n/a. This is a text-only project; there are no sensors, no
physics simulation, no reinforcement loop.

Buildable here: no. Would require a simulator, a policy training loop,
and a different evaluation harness.

## T5 — Continual learning

Canonical: Parisi et al. 2019 (continual learning survey); Kirkpatrick
et al. 2017 (EWC).

Status: not present. Every run starts from the same config, same
weights, same prompt. Nothing from run N informs run N+1.

Buildable here: partially. Weight-level continual learning needs
training (see T1). What can be built here is **episodic memory**: a
persistent store of (goal, plan, outcome) tuples that biases the
planner prompt on similar goals in future runs. That is real and
testable — but it is closer to "memory retrieval" (T7) than to
catastrophic-forgetting-resistant continual learning.

## T6 — World models

Canonical: Ha & Schmidhuber 2018 (World Models); LeCun 2022 (JEPA
position paper).

Status: not present.

Buildable here: only as a toy. A small transition model that predicts
next state given current state and action, trained on a synthetic
environment (e.g., a 2D grid where actions move a token). Measures:
does an explicit world model improve planning over reactive action
selection on the toy? Not a claim about AGI — a claim about whether
the *idea* is testable in this shell.

## T7 — Retrieval augmentation

Canonical: Lewis et al. 2020 (RAG).

Status: partially present. `memory/` has chunker, embeddings, retriever,
`memory_search` tool. End-to-end RAG is usable from the REPL.

Buildable here: mostly done. What's missing is **multi-hop retrieval**
(chained retrievals where each query depends on the previous result)
and **retrieval quality measurement** (does RAG improve accuracy on
knowledge-heavy benchmarks vs. no retrieval?).

## T8 — Self-models / calibration

Canonical: Kadavath et al. 2022 (language models mostly know what they
know).

Status: not present. The system cannot say "I don't know how to do
this" before attempting; it just attempts and reports.

Buildable here: yes — **building now** (`src/agi/trajectories/t8_calibration.py`).
Measures: is the model's self-estimated plan-success probability
correlated with actual success? Brier score and expected calibration
error (ECE) on the current benchmarks.

## T9 — Compositionality

Canonical: Lake & Baroni 2018 (SCAN benchmark).

Status: not present.

Buildable here: yes — a benchmark, not a model change. Construct
compositional goals (e.g., "list the workspace, then for each file,
read it, then write its length to a summary") where some compositions
appear in the "training" set and others do not. Measures: does the
planner generalize to novel primitive compositions?

## T10 — Neural-symbolic

Canonical: Garcez & Lamb 2020 (neurosymbolic AI survey).

Status: partially present. `Plan.validate_graph` is a symbolic check
over a neural-generated structure. Typed plan calculus (see
`TYPED_PLAN_CALCULUS.md`) is a stronger instantiation of the same
idea.

Buildable here: yes, partially. What's missing is the **other
direction** — symbolic → neural. Would require the symbolic checker
to propose *partial* plans that the neural model completes. That's a
design problem before it's a code problem.

## What this project can actually contribute

Of the 10 trajectories, this repo can build measurable versions of:

- **T2** (self-consistency) — buildable now
- **T5** (episodic memory) — buildable next
- **T6** (toy world model) — buildable as a toy
- **T8** (calibration) — buildable now
- **T9** (compositional benchmark) — buildable next
- **T10** (partial, neural-symbolic) — partially built via typed plans

For each of these, the *measurement* is the deliverable. A calibration
number, an accuracy delta between single-sample and self-consistent
planning, a compositional accuracy on unseen composites — those are
testable, honest, and useful.

## The honest meta

None of these is AGI. Adding T2 + T5 + T6 + T8 + T9 to the current shell
gives a system that:

- Reasons by sampling (T2)
- Remembers episodic outcomes (T5)
- Predicts next state in a toy environment (T6)
- Estimates its own capability (T8)
- Tests compositional generalization (T9)

A system with those five properties is *measurably* more capable than
the current shell. It is not AGI. The capabilities AGI requires that
are still absent:

- **Transfer beyond the training distribution** — still untested at scale
- **Weight-level learning from experience** — T1, not buildable here
- **A model of the world that predicts without being told** — T6 is a toy
- **Genuine grounding** — T4, not buildable here
- **Self-improvement** — not a trajectory on this map, and not buildable

The map is what research looks like when it is honest: ten plausible
directions, four to six of them measurable here, none of them a claim
of AGI.

If you want a "percentage," the honest number is **0%**, and the reason
is that AGI is not a percentage — it's a category the current
architecture is not in. What you get by building the trajectories above
is a system with measurable capability increments. That's the whole
claim.
