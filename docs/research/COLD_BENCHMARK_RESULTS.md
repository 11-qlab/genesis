# Cold Benchmark Results

A "cold" benchmark is one that was never tuned against before the first
run. Under DECISIONS D016, cold benchmarks are the only measurements that
can support a capability claim.

## Correction notice

An earlier version of this file reported single-run accuracies as if they
were the result. They were not. The numbers below have been revised to
reflect the sampling reality:

- **error_recovery.jsonl: 5 runs of `openai/gpt-oss-120b`** produced
  `5/8, 6/8, 5/8, 6/8, 6/8`. Mean = **0.7000**, range **0.6250–0.7500**.
  A single-run value of 0.6250 (step 33) and a single-run value of 0.8750
  (step 35) are both inside the noise.
- **task_chain.jsonl: 2 completed runs** produced 0.9000 and 0.9000. A third
  run did not complete before this session ended. Insufficient n for a
  point estimate, but the two samples agreeing is weak evidence of
  determinism on this benchmark. Stated as: "0.90 in two runs, n=2."

## error_recovery.jsonl

**What it tests:** given a guaranteed first-step failure (read a nonexistent
file), does the Coordinator's one-step reflection loop produce a recovery
plan that actually fixes the failure and lets the retry succeed?

**What we know:**

- Coordinator behaviour is deterministic: it fires the recovery prompt,
  calls the model, records `step.retry`, calls the recovery tools,
  records `step.recovery`, retries the original tool, records the outcome.
- Model behaviour is noisy. 5 runs produced scores between 5/8 and 6/8
  (0.625 – 0.750). The failures are "recovery plan ran but did not
  include `fs_write`" — the same failure shape appears in 2 to 3 items per
  run.
- At n=8 items per run and 5 runs, the 95% CI on the mean is roughly
  0.45–0.95. **Do not quote 0.70 as a capability number.** Quote it as
  "0.70, 5 runs of 8 items, wide CI."

**What we don't know:**

- Whether the wide interval is model nondeterminism or something in the
  harness (temperature is 0; the responses still differ).
- How qwen/qwen3.8-27b got 0/8 in one run. The failure detail was not
  captured. That's a follow-up, not a result.

## task_chain.jsonl

**What it tests:** multi-step plans with a specific tool sequence.

**What we know:**

- 2 completed runs of `openai/gpt-oss-120b` each produced 9/10 = 0.9000.
- The single failure in both runs is `tc-09`, which produces
  `fs_read("{{s1.result[0].text}}")` — Jinja-style variable substitution
  the platform does not implement.
- That failure is a **platform limitation**, not a model limitation.

**What we don't know:**

- A third run would be needed to say "0.90 stable." Two runs is
  suggestive, not conclusive.

## What neither number supports

- Any generalization claim. These are 8 and 10 items, respectively. Even
  0.70 ± 0.25 on 40 total items is not a claim about "error recovery" in
  general.
- Any comparison between models. `qwen3.8-27b` produced 0.80 on task_chain
  (single run) and 0.00 on error_recovery (single run, cause unknown).
  Neither is a result; both are samples.
- Anything about AGI. Neither benchmark touches general reasoning.

## The rule this project learned the hard way

A single run is not a result. Any number that goes into the repo as a
finding must be a mean over at least 3 runs with the range stated. If the
range spans more than 0.15, do not write a point estimate — write
"insufficient n."

See `bench/README.md` for the full rule.
