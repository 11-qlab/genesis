# Benchmarks frozen 2026-10-20

All four `.jsonl` files in this directory are frozen. They were used as the
target of prompt-tuning in this session, so they cannot be used to claim
generalization. They are correct as **regression tests** — any change that
drops their accuracy is a regression against this baseline — but they are
not evidence about the model's capabilities beyond these items.

| file | items | accuracy against openai/gpt-oss-120b | when |
| --- | --- | --- | --- |
| workspace_list.jsonl | 3 | 1.0000 | before any tuning |
| workspace_list_hard.jsonl | 20 | 1.0000 | after mode aliases + vague-verb rule |
| memory_search.jsonl | 3 | 1.0000 | before any tuning |
| memory_search_hard.jsonl | 15 | 1.0000 | after memory-domain rule |

To make a generalization claim you must add a fresh benchmark that was
**never run before the prompt was written**. Anything else is a regression
test, not a measurement of capability.

## New benchmark added 2026-10-20: `task_chain.jsonl`

10 items requiring 2–4 dependent tool calls per goal. First run was cold:
the planner prompt was tuned against the previous four benchmarks and was
NOT tuned against task_chain before this run.

| file | items | accuracy against openai/gpt-oss-120b | when |
| --- | --- | --- | --- |
| task_chain.jsonl | 10 | 0.9000 (2 runs) | first two runs, cold, both 9/10 |

The single failure (`tc-09`) is instructive: the model produced
`fs_read("{{s1.result[0].text}}")`, which is Jinja-style variable
substitution that the platform does not implement. The model correctly
identified that chained steps need data passing and wrote syntax hoping
it would resolve. This is a **capability limit of the platform**, not a
model hallucination. Fixing it requires a feature: variable interpolation
between plan steps. That has not been added; the benchmark's `expect_sequence`
check correctly flags the item as failed.

If a future session wants to improve this number, that is a feature addition,
not a prompt change. Under D016, if the feature is added after seeing this
failure, task_chain becomes a tuned benchmark too, and the next fresh
benchmark is the only way to claim generalization again.

## New benchmark added 2026-10-20: `error_recovery.jsonl`

8 items, all require: initial `fs_read` on a nonexistent file → Coordinator
produces a recovery plan → retry succeeds. First runs were cold — nothing
in the planner prompt mentions the recovery path.

**Correction notice.** An earlier entry in this file recorded a single-run
accuracy of 0.6250 as the result. That was one sample. Five runs of
`openai/gpt-oss-120b` produced:

| run | passed/total |
| --- | --- |
| 1 | 5/8 |
| 2 | 6/8 |
| 3 | 5/8 |
| 4 | 6/8 |
| 5 | 6/8 |

Mean = 0.7000. Range = 0.6250–0.7500. 95% CI on the mean spans roughly
0.45–0.95. **Do not quote this as a point estimate.** The correct phrasing
is: "0.70 mean over 5 runs of 8 items, wide interval."

See `bench/README.md` for the sampling rule that this correction produced.


## Measurements batch 2026-10-20 (four blocks, key-rotated)

All four runs below used `--delay-ms 2000` with the 9-key `AGI_API_KEYS`
pool. `contaminated: false` on every block (0 items rate-limited).

| file | items | accuracy | strategy | other metric |
| --- | --- | --- | --- | --- |
| `compositional.jsonl` | 20 | 1.0000 | greedy | — |
| `task_chain.jsonl` | 20 | 0.9000 | greedy | — |
| `task_chain.jsonl` | 20 | 0.9500 | self-consistent k=3 | mean_agreement 0.7833 |
| `error_recovery.jsonl` | 20 | 0.6000 | calibration | brier 0.2500, ece 0.1000 |

**Status per bench:**

- `compositional.jsonl` — one clean run at 1.0. The baseline/novel split
  was not extracted; see `docs/research/FOLLOW_UPS.md` item F1.
- `task_chain.jsonl` — greedy reproduces the prior baseline (0.90). One
  self-consistent run at 0.95. Whether the delta is real requires
  multi-run means; see item F2.
- `error_recovery.jsonl` — brier/ECE are degenerate (arithmetic of a
  constant 0.5 estimator). Not evidence of calibration; see item F3.

## Second error_recovery calibration run (2026-10-20, F3 diagnostic)

Same configuration as the first run. `contaminated: false`.

| file | items | accuracy | brier | ece |
| --- | --- | --- | --- | --- |
| `error_recovery.jsonl` (run 1) | 20 | 0.6500 | 0.2500 | 0.1500 |
| `error_recovery.jsonl` (run 2) | 20 | 0.1500 | 0.2500 | 0.3500 |

**Range across two runs: 0.50.** Both `contaminated: false`. This
benchmark at n=20 is a smoke test, not a measurement.

**Amendment (post-analysis).** The 0.65-vs-0.15 variance above may be
partly explained by a contamination-detection blind spot fixed in
DECISIONS D019: `Coordinator._recovery_plan` swallowed `ProviderError`
from the recovery-plan call and fell through to a plain retry, which
failed as a normal tool error. Both original runs reported
`contaminated: false`, but one or both may have been rate-limited on
the recovery call with no way for `classify()` to see it. The two
numbers must be re-run after that fix before the variance finding is
trusted.

## error_recovery post-D019 re-measurement (2026-10-20)

Three runs after DECISIONS D019 fix:

    run 1: 0.7000  (14/20)  contaminated: false
    run 2: 0.8000  (16/20)  contaminated: false
    run 3: 0.8000  (16/20)  contaminated: false

Mean: **0.7667**. Range: **0.10**. Under `bench/README.md`'s threshold
(spread <= 0.15), this is a usable point estimate.

The prior numbers (0.65, 0.15) were contaminated by the D019 blind spot
and should be discarded. See `docs/development/DECISIONS.md` D019 and
`docs/research/T2_T8_T9_RESULTS.md` Amendment 3.

## T8 calibration - corrected 2026-10-20

Prior T8 records claimed "brier 0.25, ECE 0.15, model returns constant 50,
degenerate." That was wrong. The 50s were a `max_tokens=16` truncation
artifact - the model started reasoning, ran out of budget, no number
emitted, parser fell back to 50.

Re-run with `max_tokens=200`:

    er-01: est 65
    er-02: est 85
    er-03: est 10
    ...
    er-20: est 5

    parsed_ok: 20/20
    Estimates: 0, 5, 8, 10, 15, 25, 40, 60, 65, 85
    Mean ~32, median ~20, range 0-85

**T8 IS measurable.** The model produces a meaningful self-estimate
distribution when given room. Whether those estimates are *calibrated*
(correlate with actual success) requires a calibration-strategy run at
safe pacing - not yet done. Prior brier/ECE numbers were computed on
fallback 50s and are meaningless.

Item er-15 shows a false-positive parse (est=8 from reasoning text).
Follow-up: require a numeric-only response before accepting the parse.

## T8 calibration — first real measurement (2026-10-20)

    benchmark:     error_recovery.jsonl (20 items)
    strategy:      calibration
    accuracy:      0.7000 (14/20)
    brier:         0.388115
    ece:           0.4305
    contaminated:  false
    rate_limited:  0

Brier 0.388 > 0.25 = worse than constant-0.5 baseline. ECE 0.43 =
severe under-confidence. First real T8 measurement. Negative finding.

## T11 §1 broad transfer screen (2026-10-20)

| benchmark | 5-tool | 20-tool | delta | rate_limited |
| --- | --- | --- | --- | --- |
| workspace_list_hard | 1.00 | 0.90 | -0.10 | 1 |
| task_chain | 0.95 | 0.90 | -0.05 | 0 |
| error_recovery | 0.85 | 0.45 | -0.40 | 0 |

Single-run screen. Only the -0.40 on error_recovery is clearly outside
noise. Mechanism partial (one item traced, 11 failing items not
itemized). See docs/research/T11_BROAD_TRANSFER.md.
