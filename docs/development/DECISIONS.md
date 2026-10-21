# Decisions (ADR-style)

## D001 — stdlib `urllib` for the OpenAI-compatible client
`httpx` is not installed and disk is constrained. `urllib.request` covers
everything the client needs: JSON POSTs, SSE streaming via `response` iteration,
custom headers, timeouts. Trade-off: no connection pooling, no HTTP/2. Acceptable
at CLI scale. Revisit when `httpx` is a hard requirement.

## D002 — SQLite, not an ORM
Two tables, WAL, foreign keys. Zero migration machinery today. The store API is
small enough that a swap to Postgres later is a mechanical change.

## D003 — `Plan.validate_graph` rejects forward references
A `depends_on` entry must name a step defined earlier in the list. This makes
execution order fully determined by the plan JSON and eliminates any need for
topological sorting at runtime. The test for cyclic plans therefore asserts a
"depends on later step" message, not "cycle"; the cycle branch is defense in
depth and is currently unreachable through the validator.

## D004 — Echo goal extraction
`EchoProvider` returns a real `Plan` JSON when it sees the `PLAN` marker.
The `goal` field is extracted from `"PLAN for goal: <goal>"` rather than echoing
the whole planner prompt, so end-to-end tests assert on user-visible state
(the plan's `goal` equals the goal string) rather than an implementation detail.

## D005 — Sandbox root is created by the CLI, not by the tool
`_resolve` correctly rejects a nonexistent root (treated as escape). Callers
that want `fs_list(".")` to succeed must `mkdir -p cfg.tools.fs_root` first.
The CLI does this in `_boot()`; tests must do it explicitly. Centralizing the
mkdir in the CLI keeps the tool itself pure and side-effect-free.

## D006 — No `pip install -e .`
Installing the editable package would pull `hatchling` to build the wheel and
`pip` will try to fetch it. That is a network side effect the training
restriction also forbids in spirit. Instead `bin/agi` wraps
`PYTHONPATH=<repo>/src python3 -m agi`, which is exactly what the console
script would do after install.

## D007 — HTTP API binds loopback by default
`agi serve` refuses to start on a non-loopback host without `--allow-remote`.
Rationale: the process can execute tools against a sandboxed filesystem, and
mistakenly exposing it to a LAN interface turns a local research tool into a
remote one. The flag is explicit; the default is safe.

## D008 — API error model
All responses are JSON with an `ok` boolean. `400` for caller errors (bad JSON,
missing `goal`, non-integer run id), `404` for unknown path or run, `422` for
AGI-level failures (plan invalid, provider failed). Success is `200` with
`{"ok": true, ...}`. No `5xx` from the handler itself — transport errors
surface as exceptions and are logged; the API is a thin wrapper over the same
`Coordinator` the CLI uses, so its failure modes are the coordinator's.

## D009 — Evaluation tables live in the same SQLite file
`eval_runs` and `eval_items` are additive tables in `state/agi.sqlite3`. No
migration is needed because the schema is `CREATE TABLE IF NOT EXISTS`. A
separate DB would complicate joins from an eval item back to the run that
produced it. If the DB grows too large for one file, the split points are
obvious and do not affect the API.

## D010 — Benchmarks bundle with the repo
`bench/workspace_list.jsonl` ships in the repo so `agi eval run` works on a
clean checkout against the echo provider. New benchmarks are just additional
`.jsonl` files; `--bench` selects which one. No download, no manifest.

## D011 — Training is disabled by default and at three layers
A caller who genuinely wants to train must pass through three gates:

1. `agi train run --yes-train` — the CLI refuses without the flag.
2. `Trainer.run()` — an adapter that is not implemented raises a clear
   message; the CLI catches this and exits `2`.
3. No adapter ships in the repo. Building one is an explicit act.

The estimator (`agi train estimate`) and `agi train prepare` are safe to call
without `--yes-train`: they write no checkpoints and start no subprocesses.
This is intentionally redundant so that removing any single gate does not
silently enable training.

## D012 — `memory_search` lives under `memory/`, not `tools/`
`tools/` is intentionally dependency-minimal (core + pydantic). The memory
tool needs `Retriever`, `HashEmbedding`, and `numpy`, none of which belong in
`tools/`. Registering the tool in `_boot()` (the only place that wires
subsystems together) keeps the dependency graph clean and lets the platform
run without `memory_search` if `numpy` is missing — the registration is
guarded.

## D013 — `Benchmark.before_each` instead of a benchmark subclass
Stateful benchmarks (memory retrieval, future fixture-driven tasks) need to
seed store state before each item runs. Two options considered:

1. A `Benchmark` subclass with an overridden `run` method.
2. A callback field on `Benchmark` invoked by `EvalRunner` per item.

Chose (2). The runner owns the loop; a subclass would duplicate that loop and
drift. Failures in `before_each` are recorded as `status="seed_error"` items
and do not crash the run — that way a broken fixture is visible in the eval
report instead of being indistinguishable from a normal failure.

## D014 — Echo provider is plan-aware
`EchoProvider` returns a `memory_search` plan when the extracted goal matches
`search|memory|retriev`. This is a test fixture, not a heuristic in the
production path — a real model returns whatever it returns. The echo
provider exists to make end-to-end tests deterministic; its branching is
documented here so nobody mistakes it for a semantic classifier.

## D015 — Planner receives the full tool catalog, not just names
The first real-model run (Groq `openai/gpt-oss-120b`, 2026-10-20) failed 3
of 6 items, all because the model treated "list" and "notes" as filesystem
tasks. The failures named the model's exact choices: `fs_list(path="/")`,
`fs_list(path="/notes")`. The tools were described to the planner by name
only, no descriptions, no arg schemas, and no statement that `fs_*` paths
are relative to the sandbox root.

The fix was not to change the model. The fix was to give the model the
information it needed to make a defensible choice:

- Tool descriptions (from each `Tool.description` class attribute).
- Args schemas (from each `Tool.args_model.model_json_schema()`), with
  required markers.
- An explicit system-prompt rule that `fs_*` paths are relative to the
  sandbox root and absolute paths like `/` are rejected.

After that change, the same model on the same endpoint scored 6/6.

The design decision that follows from this: **the planner prompt is a
first-class interface**, not an implementation detail. It is where the
model's tool-selection behavior is determined. When a change touches that
prompt, the change is behavioral and must be measured with an eval run
before and after.

The `Planner` constructor accepts either a list of tool names (bare) or a
list of tool dicts (rich). Rich is the default in every code path that
runs an actual plan: `SimpleAgent`, `Coordinator`, the CLI `plan` command,
and the API's `/v1/plan`. Bare names are kept for unit tests that only
exercise plan-schema validation.

## D016 — Prompt tuning is bounded by the benchmark it was tuned on
Between step22 and step29, the workspace_hard score went from 0.65 to 1.00
and the memory_hard score went from 0.7333 to 1.00, all against the same
model. Every step in that improvement was a prompt or schema change written
in direct response to a specific failure on that specific benchmark:

- vague-verb rule → fixed `wl-11` ("inspect the workspace")
- fs_write mode aliases → fixed `wl-07` (model emitted `mode='w'`)
- memory-domain rule → fixed `ms-08`, `ms-12`, `ms-14`

This is not a claim that the model improved. It is a claim that the prompt
was tightened against these 35 items. If a new benchmark is added later
that was never seen during tuning, its score will be the first honest
measurement of the prompt's generalization, and it may be substantially
lower than 1.0. That is expected and correct.

**Rule going forward**: any prompt or schema change that measurably moves an
existing benchmark must be accompanied by an honest note (in STATUS or in
`bench/FROZEN.md`) that the benchmark has been tuned against. From that
moment on it is a regression test, not a capability claim.

The next capability claim requires a *fresh* benchmark. It cannot be created
by tuning the current ones.

## D019 — Recovery-plan ProviderError must propagate, not be swallowed

Found 2026-10-20 during the variance investigation on
`error_recovery.jsonl`. Two clean runs of the same benchmark gave
accuracy 0.65 and 0.15. Both reported `contaminated: false`. That
triggered a look at why so much variance could pass contamination
detection, and it turned out one failure path was masking rate limits.

**The bug.** `Coordinator._recovery_plan` had:

    try:
        return planner.plan(prompt)
    except Exception as exc:
        log.info("recovery plan unavailable: %s", exc)
        return None

When the recovery-plan call hit a 429 that survived
`OpenAICompatProvider`'s own retries, the `ProviderError` was caught and
swallowed. The coordinator fell through to the retry of the original
step, which failed on the same tool error. The run was recorded as a
**normal tool failure** — with a tool-error message in the item's
`detail`, not a rate-limit one. Contamination detection
(`evaluation/contamination.py`) checks `detail` for "429" / "rate limit"
markers. It found neither. `contaminated: false`.

**Consequence.** A run that was actually rate-limited looks exactly like
a run where the model just produced bad recovery plans. That is a
plausible partial explanation for the 0.50 accuracy swing between the
two calibration runs, and it means both `contaminated: false` results
are now suspect until the fix has been run and those experiments
repeated.

**The fix.** `_recovery_plan` now catches `PlanValidationError` (real
recovery failure) separately from `ProviderError` (harness failure). The
former returns `None` so the caller falls back to plain retry. The
latter re-raises so `Coordinator.execute` records `run.failed` with the
full 429 in the summary, and `EvalRunner` propagates the message into
the item's `detail`, and `classify()` marks the run contaminated.

**Tests.** `tests/unit/test_recovery_provider_error.py` (Coordinator
level) and `tests/integration/test_recovery_contamination.py` (EvalRunner
level) both fail without the fix and pass with it.

**Re-verification required.** The two `error_recovery.jsonl` numbers
(0.65 and 0.15) must be re-run after this fix. If they still swing by
0.50 with both `contaminated: false`, that is genuine model variance at
n=20 and FOLLOW_UPS F5 (grow to 100 items) stands. If the swing reduces,
the original swing was rate-limit noise being masked.
