# Roadmap

Status legend: ✅ shipped + tested | 🟡 partial | ⬜ not started.

## Phase 1 — Foundation ✅
- Repository layout, `pyproject.toml`, `.gitignore`, `.env.example`, `LICENSE`.
- Config loader (TOML + env, pydantic-validated).
- Structured logging (text + JSON formatters).
- CLI: `version`, `doctor`, `health`, `config show`, `chat`, `plan`, `run`,
  `runs`, `show`, `tools`.
- Verification: `pytest`, `ruff check src tests`.

## Phase 2 — First vertical slice ✅
- `EchoProvider` (offline) + `OpenAICompatProvider` (stdlib `urllib`, SSE).
- CLI `chat` works against either.
- Integration test exercises `openai_compat` against a local `http.server` stub.
- Error paths: 4xx (no retry), 5xx (retry then raise), malformed JSON.

## Phase 3 — Persistence ✅
- SQLite run + event store, WAL, foreign keys.
- `agi runs`, `agi show <id>`. Event kinds: `run.started`, `plan.created`,
  `step.completed`, `step.failed`, `run.completed`, `run.failed`.

## Phase 4 — Tools and planning ✅
- Typed tool registry with pydantic-validated args.
- `fs_list`, `fs_read`, `fs_write` inside `AGI_FS_ROOT`.
- `shell` (allowlisted argv, `shell=False`, timeout).
- Planner with schema + DAG validation; `SimpleAgent` executor with wall-clock
  and tool-call budgets.

## Phase 5 — Agent orchestration ✅
- ✅ Single-agent pipeline (`SimpleAgent`).
- ✅ Bounded reflection (`Coordinator`): on first failure of a step, one
  recovery sub-plan is produced and executed, then the original step is retried
  exactly once. Hard cap on total tool calls, wall-clock budget, and
  configurable `max_step_retries`.
- ✅ Loopback HTTP API: `POST /v1/plan`, `POST /v1/run`, `GET /v1/runs`,
  `GET /v1/runs/<id>`, `GET /health`. `agi serve` refuses to bind a
  non-loopback host without `--allow-remote`.
- ⬜ Specialized agents (planner / coder / researcher / tester).
- ⬜ Dependency-aware multi-agent graph.

## Phase 6 — Evaluation and research ✅
- ✅ Benchmark protocol (`Benchmark`) + JSONL dataset loader with strict
  validation (missing `goal`, missing `expect_tool`, bad `expect_status`,
  empty file, comment lines).
- ✅ `EvalRunner` executes a benchmark against a `Coordinator`, persists
  per-item rows in `eval_items`, per-run aggregates in `eval_runs`.
- ✅ Metrics: accuracy, mean / p50 / p95 duration, unique tools, status
  counts. Report renders to JSON and Markdown.
- ✅ CLI: `agi eval run [--bench PATH] [--markdown]`,
  `agi eval list`, `agi eval show <id> [--markdown]`.
- ✅ Bundled benchmarks:
  - `bench/workspace_list.jsonl` — 3 items, `fs_list`, echo provider.
  - `bench/memory_search.jsonl` — 3 items, `memory_search`, seeded via
    `--seed memory`; exercises the RAG loop end-to-end.
- ✅ Regression gate: `agi eval compare <A> <B>` — accuracy delta, per-item
  regressions/improvements, tool changes, items only in one side. Read-only;
  never writes to the store.
- ✅ `Benchmark.before_each` — optional per-item hook so stateful benchmarks
  (memory retrieval, future training-set fixtures) can seed the store before
  each Coordinator run.
- ⬜ Experiment definitions with seeds (needed only when training exists).

## Phase 6.5 — Advanced reasoning (partial)
- ✅ Reasoning trace (`reasoning/trace.py`): every plan and step produces a
  trace event alongside the store record. Opt-in, no behavior change.
- ✅ Post-plan self-critique (`reasoning/critique.py`): one extra model call
  asking whether the plan's tool choices are sound. `Coordinator` accepts
  `enable_critique=True`; the CLI surfaces it later.
- ✅ Hard benchmark families: `bench/workspace_list_hard.jsonl` (20 items,
  paraphrased goals), `bench/memory_search_hard.jsonl` (15 items, seeded).
  **Both are frozen as of 2026-10-20** — see `bench/FROZEN.md` — because the
  planner prompt was tuned against them.
- ✅ 100% accuracy on all four frozen benchmarks against
  `openai/gpt-oss-120b`. This is a regression baseline, not a capability
  claim. See DECISIONS D016.
- ⬜ A fresh benchmark that was never used for tuning. This is the only
  thing that can turn the 1.0s into a real generalization claim.
- ⬜ Plan-level revision (not step-level retry): the plan as a whole is
  re-planned after a rejection or failure. Requires a redesign of Coordinator.
- ⬜ Capability self-model: "can I do X with tools T?" calibration.

## Phase 7 — Training readiness 🟡
- ✅ Training is disabled by default. `agi train` refuses to do anything
  without a config and an explicit `--yes-train` flag.
- ⬜ Dataset adapter interface (loaders, splitters, tokenizer-agnostic).
- ⬜ Resource estimator (params, tokens, memory, time).
- ⬜ Checkpoint + artifact registry (SQLite tables, path layout).
- ⬜ Training adapters for at least one framework, wired but never invoked
  without the flag.

## Phase 8 — Hardening 🟡
- ✅ Threat model, security tests, docs.
- ✅ Live `agi serve` smoke in `scripts/verify.sh`.
- ✅ `scripts/install.sh` — links `bin/agi` into `~/.local/bin` (idempotent,
  refuses to overwrite a foreign target).
- ✅ Training refusal invariant enforced by tests in
  `tests/security/test_train_refusal.py`.
- ✅ `docs/research/RESEARCH_NOTES.md` — experiment template.
- ⬜ Reproducible install into a fresh venv from a lockfile.
- ⬜ HTTP API auth (only if ever exposed beyond loopback).
- ⬜ Deployment notes / systemd unit example.

## Phase 6 — Evaluation and research ⬜
- Benchmark adapters, experiment tracking, reproducible reports.

## Phase 7 — Training readiness ⬜
- Dataset pipelines, training adapters, checkpoint registry, resource
  estimator.
- ⚠️ Training jobs must never start without an explicit `--yes-train` flag and
  a printed configuration block. Enforced at the CLI, not at the library.

## Phase 8 — Hardening 🟡
- ✅ Threat model, security tests, docs.
- ⬜ Reproducible install into a fresh venv, HTTP API, deployment notes.
