# Contributing — the batch workflow

Every change lands as one small batch, verified before the next one starts.
That workflow is what produced the current tree and it is what should keep
extending it.

## The loop

1. **Read.** `docs/development/ROADMAP.md`, `STATUS.md`, `KNOWN_ISSUES.md`.
   Pick the smallest useful next deliverable. Write it down in one sentence.
2. **Inspect.** Open the specific files the change will touch. Do not guess
   at existing API shapes.
3. **Edit.** One subsystem per batch. If the batch wants to touch three
   packages at once, split it.
4. **Static check.** `ruff check src tests`. Fix findings in place; do not
   silence them without a `# noqa` and a one-line reason.
5. **Test.** `pytest -q`. New behavior gets a test. Broken behavior gets a
   regression test that fails without the fix.
6. **Verify.** `bash scripts/verify.sh` runs the full gate: pytest, ruff,
   `agi doctor`, `agi run`, `agi eval run` (both benchmarks), `agi serve`
   health, and a fresh-copy smoke run.
7. **Record.** Update `STATUS.md` (test count, what changed), `ROADMAP.md`
   (phase status), `DECISIONS.md` (if a trade-off was made), `KNOWN_ISSUES.md`
   (if something was deferred).
8. **Commit.** One commit per batch. Message references the phase and a short
   imperative summary. Never amend a commit that has been pushed.

## Rules

- No new dependency without a `DECISIONS.md` entry explaining the disk, network,
  or compatibility cost.
- Filesystem tools stay sandboxed to `AGI_FS_ROOT`. Do not widen that scope.
- Do not touch `agi train run` without an explicit request; the three-gate
  invariant is load-bearing.
- Do not skip tests to make a commit look green. A red suite is a red suite.
- The CLI's `_boot()` is the only place that wires config → provider → tools
  → store → memory. Subsystems do not boot themselves.

## Adding a benchmark

1. Create `bench/<name>.jsonl` — each line must have `goal` and
   `expect_tool` (string or `null`); optional `expect_status`, `id`, `tags`,
   and `seed_documents` (only consumed when run with `--seed memory`).
2. Run `agi eval run --bench bench/<name>.jsonl` and verify accuracy.
   Stateful benchmarks need `--seed memory` or a custom `before_each` hook
   set from the CLI.
3. Update `docs/development/STATUS.md` with the benchmark name and accuracy.
4. Do not edit an existing benchmark after it has a baseline unless you bump
   the baseline too — otherwise regressions become invisible.

## Adding a tool

1. Subclass `agi.tools.base.Tool`. Declare `name`, `description`, and
   `args_model` (a pydantic model). Implement `run(**validated)`.
2. If the tool needs subsystems `tools/` should not import (memory, providers,
   storage), place the adapter under the subsystem that owns it — see
   `src/agi/memory/tool.py` for the pattern.
3. Register the tool from `_boot()` in `src/agi/cli/main.py`. Do not register
   it from inside `build_registry` (that would break the dependency
   ownership rules in `SYSTEM_DESIGN.md`).
4. Add an integration test that drives the tool through a `Coordinator` with
   a scripted provider — that's the path a real model uses.

## When something fails

- Capture the exact failing line and error verbatim.
- Diagnose the underlying cause, not the symptom. Retry the failing check.
- If the failure reveals a test was asserting the wrong thing, fix the test
  with a note in `KNOWN_ISSUES.md` explaining why the assertion changed.
  Silent assertion weakening is the one thing not to do.
