# AGI Platform

A modular, tested research platform for building and evaluating agentic AI
systems. It is **not** an AGI. It is infrastructure for experiments that could
eventually inform AGI research.

## Project state

| phase | status | what it delivers |
| --- | --- | --- |
| 1 — foundation | done | config, logging, CLI, tests |
| 2 — vertical slice | done | echo + openai_compat, `agi chat`, error paths |
| 3 — persistence | done | SQLite runs + events, `agi runs` / `agi show` |
| 4 — tools + planning | done | sandboxed fs, allowlisted shell, DAG-validated plans |
| 5 — orchestration | done | `SimpleAgent` + `Coordinator` + loopback HTTP API |
| 6 — evaluation | done | JSONL benchmarks, metrics, `agi eval run` |
| 7 — training readiness | partial | contracts + estimator + registry; execution gated |
| 8 — hardening | partial | threat model, security tests, `scripts/install.sh` |

Run `bash scripts/verify.sh` for the full gate. Every claim above maps to code
and a test in this repository.

The platform is **not** an AGI. It is infrastructure for experiments that could
eventually inform AGI research. No claim of consciousness, general reasoning,
or autonomous self-improvement is made anywhere in this repository.

## Install (no network needed)

    bash scripts/setup.sh

Requires Python >= 3.11 with `pydantic`, `typer`, `rich`, `pytest`, `ruff`
already installed. No `pip install` is required to run.

## Run

    bin/agi doctor
    bin/agi chat "hello"
    bin/agi plan "list the workspace"
    bin/agi run  "list the workspace"
    bin/agi runs
    bin/agi show 1

The `bin/agi` wrapper sets `PYTHONPATH=src` and calls `python -m agi`, which
is exactly what the installed console script would do.

## Point at a real model (DeepSeek or any OpenAI-compatible endpoint)

    export AGI_PROVIDER_KIND=openai_compat
    export AGI_PROVIDER=deepseek
    export AGI_BASE_URL=https://api.deepseek.com/v1
    export AGI_MODEL=deepseek-chat
    export AGI_API_KEY_ENV=AGI_API_KEY
    export AGI_API_KEY=sk-...
    bin/agi health
    bin/agi chat "say hello"

Nothing is read from disk for the key. `agi doctor` prints the env-var name,
never the value.

## Evaluation

    bin/agi eval run --bench bench/workspace_list.jsonl
    bin/agi eval run --bench bench/workspace_list.jsonl --markdown
    bin/agi eval list
    bin/agi eval show 1 --markdown

Benchmarks are JSONL files. Each line has `goal`, `expect_tool` (string or
`null`), optional `expect_status`, `id`, `tags`. Add new files under `bench/`
and pass them with `--bench`.

## Document memory

    bin/agi memory ingest notes.txt
    bin/agi memory search "sandbox filesystem" -k 3
    bin/agi memory list

Embeddings default to `HashEmbedding` (offline, deterministic). When
`AGI_PROVIDER_KIND=openai_compat`, the CLI uses the same base URL for
embeddings, which works with DeepSeek and any OpenAI-compatible server.

The `memory_search` tool is registered into the ToolRegistry automatically;
a plan can call it like any other tool. `bench/memory_search.jsonl` exercises
this end-to-end:

    bin/agi eval run --bench bench/memory_search.jsonl --seed memory

## Interactive REPL

    bin/agi repl
    >> list the workspace and tell me what you see
    >> create a file called notes.txt with the word hello
    >> :history
    >> :quit

    # one-shot, same machinery, no REPL loop
    bin/agi repl once "list the workspace"

Each turn runs a full plan-execute cycle against the current provider.
The last four turns are summarized into the next goal's context so the
planner can reference earlier work. `:clear` wipes history. Raw results
without a summarizer call: `agi repl --raw`.

## Local HTTP API

    bin/agi serve --port 8000

    curl http://127.0.0.1:8000/health
    curl -X POST http://127.0.0.1:8000/v1/plan -d '{"goal":"list workspace"}'
    curl -X POST http://127.0.0.1:8000/v1/run  -d '{"goal":"list workspace"}'
    curl http://127.0.0.1:8000/v1/runs
    curl http://127.0.0.1:8000/v1/runs/1

Loopback only by default; `--allow-remote` is required to bind any other
address. The API is a thin wrapper over the same `Coordinator` the CLI uses.

## Training

Training is disabled by default at three independent gates:

1. `agi train run` refuses without `--yes-train`.
2. `Trainer.run` is unimplemented; the CLI exits 2 with a clear message.
3. No adapter ships in the repo.

Safe commands: `agi train estimate` (resource estimate), `agi train prepare`
(validate a job spec and record it).

## Verify

    bash scripts/verify.sh

Runs pytest, ruff, `agi doctor`, a full `agi run`, `agi eval run`, and a live
`agi serve` health check.

## Architecture and policy

- [`docs/architecture/SYSTEM_DESIGN.md`](docs/architecture/SYSTEM_DESIGN.md)
- [`docs/development/ROADMAP.md`](docs/development/ROADMAP.md)
- [`docs/development/STATUS.md`](docs/development/STATUS.md)
- [`docs/development/DECISIONS.md`](docs/development/DECISIONS.md)
- [`docs/development/KNOWN_ISSUES.md`](docs/development/KNOWN_ISSUES.md)
- [`docs/development/CONTRIBUTING.md`](docs/development/CONTRIBUTING.md)
- [`docs/research/RESEARCH_NOTES.md`](docs/research/RESEARCH_NOTES.md)
- [`docs/security/THREAT_MODEL.md`](docs/security/THREAT_MODEL.md)
