# System Design

## Scope

A modular research platform for building and evaluating agentic AI systems.
It is not an AGI and makes no claim of consciousness, general reasoning, or
autonomous self-improvement. Every claim in this tree maps to code and a test.

## Layered architecture

    CLI  →  core (config / logging / lifecycle / registry)
         →  providers (echo, openai_compat)  →  reasoning (planner, DAG)
         →  tools (fs sandbox, allowlisted shell)  →  agents (SimpleAgent, Coordinator)
         →  storage (sqlite runs + events + eval_runs + eval_items)
         →  observability (health)
         →  memory (documents, chunker, embeddings, FlatIndex, Retriever)
         →  evaluation (dataset, benchmark, runner, metrics, report, compare)
         →  api (stdlib ThreadingHTTPServer, loopback only)
         →  training (contracts, estimator, checkpoint registry; no execution)

Dependencies only point downward. Nothing in `providers` imports `agents`.
Nothing in `tools` imports `agents`. `agents` is the only module that pulls
planner + tools + store together.

## Layered ownership (what may import what)

-          → stdlib + pydantic only. No sibling imports.
-     → . Never , , , .
-     → , . Never , , .
-         → , pydantic. Never , .
-       →  only.
-        → , , , , .
-  → , , ,  (read-only use).
-    → , , , , .
-           → , , , , .
-      →  only. Execution lives behind the CLI's .
-           → everything, composed once in .

Violations are caught by eye and by import-time circularity; a lint rule to
enforce this mechanically is a future task.

## Component contracts

- `providers.base.Provider` — `complete`, `stream`, `health`. Implementations:
  `EchoProvider` (offline, deterministic), `OpenAICompatProvider` (any server
  exposing `/v1/chat/completions`; stdlib `urllib` only).
- `reasoning.schemas.Plan` — validated plan model. `validate_graph` rejects
  unknown tools, dangling dependencies, forward references, duplicates, and
  cycles. `topo_order` returns a deterministic execution order.
- `tools.base.Tool` — `name`, `description`, `args_model` (pydantic), `run`.
  `ToolRegistry.execute` always validates args against the tool's model before
  calling `run`, so model-generated args cannot bypass the schema.
- `agents.simple.SimpleAgent` — takes a provider, a tool registry, a store, and
  a runtime budget. Its only job is plan → execute → record. Every step
  produces one event; the run is always terminated either `succeeded` or
  `failed` with the reason recorded.
- `storage.sqlite.Store` — tables `runs`, `events`, `eval_runs`, `eval_items`,
  `memory_documents`, `memory_chunks`. WAL, foreign keys. No ORM. The store is
  the single source of truth for run history, eval history, and ingested docs.
- `memory.Retriever` — chunk → embed → store → index → search. Embeddings are
  either hash-based (offline, deterministic) or `openai_compat` (same
  provider base URL). The FlatIndex is numpy-only and reloaded on cache miss.
- `memory.MemorySearchTool` — the retrieval tool the planner sees. Registers
  into the ToolRegistry from `_boot()` only.

## Security boundary

- `AGI_FS_ROOT` is the only writable filesystem root for tools. `_resolve`
  rejects any path whose resolved form is neither the root nor a descendant.
- Shell tool is disabled by default. When enabled it is allowlisted by
  executable name and executed without `shell=True`, so metacharacters cannot
  chain commands.
- API keys live only in `os.environ[cfg.provider.api_key_env]`. Never printed,
  never logged, never persisted.

## Configuration flow

1. Read TOML file (default `config/default.toml` unless `AGI_CONFIG` is set).
2. Overlay `AGI_*` env vars.
3. Validate with pydantic. Unknown `provider.kind` → hard fail.

An explicit config path that does not exist raises `ConfigError` rather than
silently falling back to defaults.
