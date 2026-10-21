# What AGI Would Actually Require

This is a research document. It contains no claims that this project achieves
AGI, is close to AGI, or has a path to AGI. It is a list of capabilities
researchers use to argue that a system is **not** a general intelligence,
because that is more useful than a list of what it is. Every item here is a
gap in the current codebase, and every gap is bounded — no hand-waving about
"emergence."

## 1. Broad transfer

An AGI must handle arbitrary tasks, not just ones from a benchmark. The
current codebase handles exactly two benchmark families:
`fs_list`-style listing and `memory_search`-style retrieval. Both involve
one-step plans against small tool catalogs.

**Gap**: transfer to tasks outside the tool catalog. The measurement is
straightforward: expand the tool catalog to 50 tools and rerun the current
benchmarks. If accuracy collapses, transfer is bounded by catalog size. That
has not been measured here. It is the single cheapest next measurement.

## 2. Multi-step planning with backtracking

Current `Coordinator` supports one recovery plan and one retry. Real planning
requires trying a branch, observing it fail, and revising the whole plan, not
just the failed step. This is exactly what `LLM+P` and `Tree-of-Thoughts`
attempt; neither is implemented here.

**Gap**: no plan-level revision. A plan either succeeds as written or the
run fails after one retry. This is not AGI; it is bounded execution.

## 3. Self-model

An AGI needs to know what it does not know. The current `SimpleAgent` reports
accuracy after the fact. It cannot say "I do not know how to do this" before
attempting the plan, because it has no model of its own capability.

**Gap**: no capability model. A first experiment would ask the model
"can you do X with tools T?" and check calibration against ground truth.
That has not been measured.

## 4. Causal reasoning

The current system reasons about the *format* of tasks (JSON, DAGs,
schemas). It does not reason about *why* something is true. If a tool
fails because a file is missing, the system records the failure. It does
not infer "the file was missing because the writer step did not run",
because that requires a causal model.

**Gap**: no causal structure. A benchmark for this would need to test
counterfactual reasoning, which is currently unsupported.

## 5. Continual learning from deployment

The current system has no state that improves between runs. Every run starts
fresh from the same config. It cannot get better at the benchmark by running
it more times.

**Gap**: no learning from experience. Every experiment trains a model
separately. That's fine for research; it's not general.

## 6. Grounded reference

The current system operates on strings and tool calls. It has no notion of
grounding (a token that points at a real object in the world that the system
can verify against). A tool call is a string instruction; the sandbox either
executes it or rejects it. That is not grounding; it is a hard validation
gate. Real grounding would require a check like "this file exists and its
content matches what I retrieved" — a soft link, not a schema.

**Gap**: none. Grounding is not a research problem this project is
attempting. Do not conflate schema validation with grounding.

## 7. Evaluation breadth

Today: 6 + 20 + 15 items across two benchmark families. This is not enough
to claim anything. A serious claim would need tens of thousands of items
across many task families, with inter-annotator agreement on expected
behavior.

**Gap**: measurement breadth. The current benchmarks are useful as
regression tests. They are not useful as claims about generality.

## What this document is really for

It exists so that the next person — including future me — has a checklist to
hold against any new claim. When someone says "this system now reasons," the
question is: which of §1–§7 moved, and by how much, on what benchmark.

The honest answer today is: none of them moved, and none are being attempted
directly. What moved today is that the platform executes real models end-to-end
and produces reproducible accuracy numbers on bounded benchmarks. That is
called infrastructure, not intelligence.

If you want to go "beyond" this project, the path is §1 first (broaden the
tool catalog) then §2 (branch-revise planning). Those are measurable. Anything
else is talk.
