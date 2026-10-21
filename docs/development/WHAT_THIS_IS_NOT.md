# What this project is not

Written down so that no one — including me, including a future me, including
anyone who reads the README — can quietly move the goalposts.

## Not an AGI

There is no algorithm in `src/agi/` that reasons. `Planner` sends a prompt and
parses JSON. `SimpleAgent` and `Coordinator` walk the resulting plan. `memory/`
is a chunker plus a hash sketch plus a linear dot-product. `EchoProvider` is a
lookup table that returns the plan the benchmark wants. None of this is
intelligence. It is a runtime that a model would sit on top of.

## Not an ASI and not on a path to one

ASI is not a code-writing exercise. No known algorithm achieves it. Anyone
claiming otherwise in a shell session is fabricating.

## Accuracy numbers are harness statements

`agi eval run` returns accuracy. That number means: the runner scheduled steps,
the tool executed, storage persisted rows, metrics aggregated. It does **not**
mean: the model reasoned well.

Concretely:

- `bench/workspace_list.jsonl` at 1.0 against `echo` means: the regex in
  `src/agi/providers/echo.py` matched "list" and returned a valid `fs_list`
  plan; the fs sandbox executed; the row was stored. The model contributed
  nothing.
- `bench/memory_search.jsonl` at 1.0 against `echo` with `--seed memory` means:
  the exact documents the query needs were planted by the fixture, the hash
  embedding matched them lexically, the `memory_search` tool returned at least
  one hit. The system did not "find" the documents; the fixture gave them to it.

`agi eval explain <run_id>` prints this distinction for any stored run.

## The 3 training gates are load-bearing

`agi train run` refuses at three independent layers: CLI flag, unimplemented
adapter, no adapter shipped. Removing any one does not enable training.
Removing all three, plus adding an adapter, is the only path.

## What it *is*

A tested framework. Config, logging, tool registry with pydantic validation,
planner with DAG validation, coordinator with bounded reflection, SQLite
persistence, loopback HTTP API, evaluation harness with two bundled benchmarks
and a compare/explain tool, retrieval with an offline default, checkpoint
registry, CLI. Every claim above maps to a test.

## What advancing actually looks like

Not more claims. More code that does one thing at a time, tested:

1. A real provider (env-only change) — the whole loop becomes a model-driven
   agent.
2. Streaming through the coordinator — needs a partial-JSON state machine.
3. A multi-coordinator task graph — design first, then code.
4. A real regression gate — two runs of the same benchmark, one diff.
5. Retrieval with a real embedding provider — `openai_compat` embeddings
   already wired; the default is the fixture.

Anything beyond that list is fabrication until it is not.
