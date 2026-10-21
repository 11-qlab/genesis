# Point at a real provider

The default provider is `echo` — a deterministic fixture. To measure what a
real model does, point the platform at any OpenAI-compatible endpoint. Three
env vars plus a key.

## One command

    export AGI_API_KEY=...             # never write this to a file
    ./scripts/point_at_provider.sh \\
        https://api.deepseek.com/v1 \\
        deepseek-chat

The script:

1. Runs `agi provider probe` — checks `/models`, `/chat/completions`,
   streaming, and `/embeddings`, each in isolation so one 4xx does not hide
   the others.
2. Runs `agi chat` — a single round-trip.
3. Runs both bundled benchmarks against the provider.
4. Prints exit codes for each phase.

The script never echoes the key. It is only read from `$AGI_API_KEY` (or the
third argument).

## Manual equivalent

    export AGI_PROVIDER_KIND=openai_compat
    export AGI_PROVIDER=external
    export AGI_BASE_URL=https://api.deepseek.com/v1
    export AGI_MODEL=deepseek-chat
    export AGI_API_KEY_ENV=AGI_API_KEY
    export AGI_API_KEY=...
    export PYTHONPATH=src

    python3 -m agi provider probe
    python3 -m agi chat "say hello"
    python3 -m agi eval run --bench bench/workspace_list.jsonl --markdown
    python3 -m agi eval run --bench bench/memory_search.jsonl --seed memory --markdown

## Interpreting the probe output

The probe returns a JSON report. Read it top-down:

- `credential_present` — `true` if the env var is set. Does not tell you the
  key is *valid*; the subsequent checks do.
- `checks.models` — some providers do not implement `GET /models`. `ok: false`
  here with `status: 404` is not a problem; the other checks still matter.
- `checks.complete` — the real test. If this fails with `401`, the key is
  wrong. With `404`, the base URL is wrong (often missing `/v1`). With
  `timeout`, the endpoint is unreachable from this host.
- `checks.stream` — some providers do not support `stream: true` with the
  model you selected. `ok: false` here while `complete` is `ok: true` means
  `agi chat --stream` will not work; the non-streaming path is fine.
- `checks.embeddings` — this is the one most models do not expose.
  `ok: false` with `status: 404` is normal; the memory feature falls back to
  `HashEmbedding`. To get semantic retrieval you need an embeddings-capable
  model on the same base URL, or a second provider later.

`overall_ok` is `checks.complete.ok`. That is the single field to watch.

## Interpreting the eval output

The benchmarks measure the harness *and* the model. What each tells you:

- `workspace_list.jsonl` at 1.0 against a real model means: the model
  produced a valid `fs_list` plan for three different phrasings. That is a
  real reasoning result. Every failure in `failures` names the exact
  mismatch — read it before drawing conclusions.
- `memory_search.jsonl` at 1.0 against a real model means: the model chose
  `memory_search` and returned at least one hit for each seeded query. But
  the seeds are lexical matches; a real semantic test would use a corpus the
  model has never seen. `HashEmbedding` will fail such a test; switch to
  `openai_compat` embeddings if the provider supports it.

`agi eval explain <run_id>` prints this distinction for any stored run.

## What this unlocks

With a real provider:

- `Planner` produces plans that reflect reasoning about the goal, not a
  regex. Different phrasings get different plans.
- `Coordinator`'s bounded reflection becomes meaningful — the recovery plan
  is genuinely a second model attempt, not a fixture.
- `agi eval compare` between two runs of the same benchmark becomes a real
  regression signal.
- `agi chat --stream` shows you the model's actual generation.

What it still does not unlock: general reasoning, autonomous self-improvement,
multi-step planning over unbounded horizons, or anything that would justify
the word "AGI."
