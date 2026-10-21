# Benchmarks

## Sampling rule (read before recording any number)

A single benchmark run is **one sample**. It is not a result.

A benchmark with 8 or 10 items, run once, has no meaningful point estimate.
Two runs of `error_recovery.jsonl` in this project produced 0.6250 and
0.8750 on the same model, same endpoint, same temperature, one hour apart.
That is not "the score." That is the noise.

**Rules:**

1. Fewer than 20 items ⇒ the benchmark is a *smoke test*, not a measurement.
2. Any number written into `FROZEN.md`, `STATUS.md`, or
   `COLD_BENCHMARK_RESULTS.md` MUST be a mean over **at least 3 runs**, with
   the range stated.
3. If the range spans more than 0.15, the point estimate is not usable. Write
   "insufficient n" instead of a number.
4. Single runs are fine during development — that's what they're for. They
   are not findings.

## Benchmarks in this directory

| file | items | purpose |
| --- | --- | --- |
| `workspace_list.jsonl` | 3 | smoke test |
| `workspace_list_hard.jsonl` | 20 | paraphrased listing goals |
| `memory_search.jsonl` | 3 | smoke test |
| `memory_search_hard.jsonl` | 15 | paraphrased retrieval goals |
| `task_chain.jsonl` | 10 | multi-step execution |
| `error_recovery.jsonl` | 8 | bounded reflection |
| `workspace_list_hard_a.jsonl` / `_b.jsonl` | 10 each | rate-limit halves |

Every file here is a **regression test**: it says "the platform has not
lost ground on this specific item set." None of them is a capability
claim, and none of them is a generalization claim — see `FROZEN.md` and
DECISIONS D016.

## Contamination rule (added 2026-10-20)

A run is **contaminated** if more than 10% of its items failed with a
rate-limit or billing error. The runner detects this automatically:

- `detail` field contains `429`, `rate limit`, `insufficient balance`,
  `quota exceeded`, or `402`
- More than 10% of items match that pattern
- The run's `status` is set to `contaminated`
- `agi eval run` exits with code 3 (distinct from accuracy failure = 1)
- The markdown report starts with a `> **CONTAMINATED**` banner

**Contaminated runs are discarded, not averaged.** A session requires
≥3 *clean* runs to produce a usable number. The 2026-10-20 typed_chain
experiment failed this rule: runs were 20/20, 14/20, 0/20, with runs 2
and 3 partially or fully rate-limited. None of those three runs are
usable as a measurement.

This rule exists because a 20-item run at Groq's 8k TPM free tier is
mathematically guaranteed to exceed the limit — 40,000 tokens in ~100
seconds = 24,000 TPM. The formula is not the model's fault; it is the
experiment's pacing.

**Before running any benchmark:**
1. Compute `items × ~2000 tokens` → total tokens per run
2. Divide by expected wall time in minutes → effective TPM
3. If effective TPM > tier limit, add pacing or shrink the prompt

See `docs/research/PACING.md` for the formula.
