# Research Notes — Template

Copy this file to `docs/research/<YYYY-MM-DD>-<short-slug>.md` for each
experiment. Do not delete old notes; the running history is the point.

---

## Title

(one line)

## Date

YYYY-MM-DD

## Question

What are we trying to learn? State it as a falsifiable question.

## Hypothesis

What do we think will happen, and why? One paragraph.

## Setup

- Platform commit: (paste `git rev-parse HEAD` if using git)
- Provider: `echo` | `openai_compat (<model>)` | other
- Tools enabled: e.g. `fs_list, fs_read`
- Benchmark: `bench/<name>.jsonl`
- `agi eval run` output (paste the JSON, or reference `eval_run_id`)

## Result

- Accuracy: N/M = X.XX
- p50 / p95 latency: X / Y ms
- Notable failures (paste per-item `detail` from the JSON report):

| item_id | status | detail |
| --- | --- | --- |
| | | |

## Interpretation

What does the result mean? Distinguish measurement from inference.
- **Measured:** (facts that follow from the numbers above)
- **Hypothesised:** (explanations that need a follow-up experiment)

## Next experiment

The single smallest change that would test the hypothesis. Be specific.

## Assumptions and caveats

- Provider determinism / sampling temperature
- Whether the benchmark is representative
- Any environment differences from the last run
