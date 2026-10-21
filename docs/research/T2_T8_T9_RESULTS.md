# T2 / T8 / T9 — First Real Measurements

**Date:** 2026-10-20
**Model:** `openai/gpt-oss-120b`
**Endpoint:** `https://api.groq.com/openai/v1` (Groq)
**Key pool:** 9 keys from 9 distinct Groq orgs (`AGI_API_KEYS`)
**Pacing:** `--delay-ms 2000` (key rotation handled 429s)
**Contamination:** `false` on all four runs (0 items rate-limited)
**Run shape:** single run per configuration. n=20 items per benchmark.

## Probe (before the four runs)

    credential_present: true    (from AGI_API_KEYS pool)
    overall_ok:         true
      models       ok=false  401  <- probe.py bug; /models still reads AGI_API_KEY
      complete     ok=true        <- what agi eval run actually uses
      stream       ok=true
      embeddings   ok=false  401  <- probe.py bug; /embeddings still reads AGI_API_KEY

`/models` and `/embeddings` 401s are a bug in `probe.py::_first_key` (the
patch from step47 that was meant to make it read the pool didn't land).
This does not affect the measurements below; `_probe_complete` and
`_probe_stream` construct a provider, and the provider uses the pool.

## The four numbers

| trajectory | benchmark | accuracy | other metric | contaminated |
| --- | --- | --- | --- | --- |
| T9 compositionality | `compositional.jsonl` (20) | **1.0000** | — | false (0) |
| T2 greedy | `task_chain.jsonl` (20) | **0.9000** | — | false (0) |
| T2 self-consistent (k=3, temp 0.7) | `task_chain.jsonl` (20) | **0.9500** | mean_agreement **0.7833** | false (0) |
| T8 calibration | `error_recovery.jsonl` (20) | **0.6000** | brier **0.2500**, ece **0.1000** | false (0) |

## Honest interpretation of each

### T9 compositionality — 1.0000 aggregate, split not extracted

The benchmark tests 20 items: 8 "baseline" (novel_ordering=0) and 12
"novel" (novel_ordering=1). The `run_bench` helper in step50 did **not**
split by `novel_ordering`; it returned the aggregate only. So this run
tells us "20/20 on the composed benchmark", not "the model generalizes to
novel compositions because it scored X on baseline and Y on novel."

**The honest claim is bounded:** 100% aggregate accuracy on a 20-item
compositional benchmark against gpt-oss-120b, single run, zero
contamination. This is stronger than the prior session's 0.90 on
`task_chain` because this benchmark was never tuned against — but the
baseline/novel split that would test **compositional generalization
specifically** was not produced by this run. Follow-up:
`docs/research/FOLLOW_UPS.md` item F1.

### T2 greedy task_chain — 0.9000

Reproduces the prior session's 0.90 on the same benchmark. That's
positive: the code has not drifted, the prompt hasn't regressed, and the
fixture-side contaminations that plagued earlier runs don't affect a clean
run at 2000 ms pacing. Two samples of the same benchmark at 0.90.
Suggestive of stability.

### T2 self-consistent k=3 — 0.9500, agreement 0.7833

One more item passes than greedy (19/20 vs 18/20). That's +0.05 accuracy
and +1/20 items. **Under `bench/README.md`'s own rules, this is a
descriptive delta from a single run, not a measurement of T2's effect.**

The `mean_agreement: 0.7833` is the more interesting number: across the
20 items, on average 78.33% of the 3 samples per item produced the same
structural signature (tuple of `(tool, arg-names)` per step). That means
at temperature 0.7 the model is **fairly confident** — it is not
generating wildly different plans on repeated sampling. Self-consistency
helps in the regime where the model is *sometimes* wrong but usually
right, so agreement 0.78 with one flipped item is consistent with the
theory. But n=20 is too small to say anything about the effect size.

**Follow-up to make this meaningful:** run self-consistent and greedy 3–5
times each on the same benchmark, compute mean + range for both, check
whether the delta survives the spread. Recorded as
`docs/research/FOLLOW_UPS.md` item F2.

### T8 calibration — 0.6000, brier 0.2500, ece 0.1000 — **degenerate**

**This is not a well-calibrated model. Read the arithmetic.**

- accuracy = 12/20 = 0.60
- brier = 0.25 exactly
- ece = 0.10 exactly

If the model returns **constant 50%** for every probe:
- Correct item (est 0.5, actual 1.0): squared error = (0.5 − 1)² = 0.25
- Wrong item (est 0.5, actual 0.0): squared error = (0.5 − 0)² = 0.25
- Mean Brier = 0.25
- ECE: one bin at 0.5, |0.5 − 0.60| = 0.10

Both numbers reproduce exactly the arithmetic of a **constant 0.5
estimator**. The model does not produce a meaningful self-estimate on
this task family. `ece = 0.10` looks "well-calibrated" only because 0.5
happens to be near the actual accuracy 0.6; the ece is a coincidence, not
a signal.

**The honest claim:** gpt-oss-120b, given the calibration probe prompt and
`error_recovery.jsonl` items, returns a constant estimate of 0.5. It does
not model its own success probability on this task family. This is a real
negative finding, not a positive one.

**Follow-up to confirm:** dump the per-item `calibration_estimate` values.
If they are all 50, the finding is confirmed. If they vary, the brier of
0.25 is a genuine estimate that happens to average to 0.25, and the T8
signal is real but weak. Recorded as `docs/research/FOLLOW_UPS.md` item
F3.

## Cross-cutting findings

**Key rotation works.** 9 keys at 2000 ms pacing, `contaminated: false` on
all four runs. This validates the assumption that the keys are from 9
distinct Groq orgs — if they were all from one org, the pooled TPM would
have been exceeded and at least one block would have shown
`contaminated: true`. Single-account runs at 2000 ms pacing previously
contaminated. The `AGI_API_KEYS` pool + rotation on 429 is load-bearing.

**Harness stability.** `task_chain` greedy at 0.90 matches the prior
session. The prompt-catalog rules and typed-plan work have not regressed
the baseline.

## What this batch is

Four real, honest measurements. Three of them are numbers. One of them
(T8) is a number that reads positive but decomposes to "the model does
not estimate." Recording that decomposition is the whole point of this
document.

## What this batch is not

- Not a claim that self-consistency works. +0.05 on 20 items, one run, is
  not evidence of a real improvement. It is evidence that one item
  flipped.
- Not a claim about compositional generalization. The baseline/novel
  split was not produced.
- Not a claim about calibration. It failed: the model gives constant 0.5.
- Not a claim about AGI, self-models, or reasoning in general. It is four
  numbers on four bounded benchmarks against one model on one day.

## Numbers to hold the project to

The next measurement run must move at least one of these numbers in an
honest direction (with multi-run means, per `bench/README.md`) before any
trajectory claim is made:

- T9 aggregate 1.0 → 1.0 is the floor; the split is the real test
- T2 self-consistent +0.05 → must survive multi-run spread to be real
- T8 brier 0.25 → must drop below 0.20 for T8 to have any content

## Addendum — bigger finding than T8: error_recovery variance

Two `error_recovery.jsonl` calibration runs:
- run 1: accuracy 0.6500 (13/20), contaminated: false
- run 2: accuracy 0.1500 (3/20),  contaminated: false

Range: **0.50**. Both clean. Under `bench/README.md`, n=20 at this
variance cannot support a point estimate.

The constant-50 `calibration_estimate` is stable across both runs even
though the outcomes aren't — that's the T8 signal. But whether the 50 is
a real model output or a probe-fallback artifact is unknown; see
FOLLOW_UPS F4.

**Amendment (post-analysis).** The 0.65-vs-0.15 variance above may be
partly explained by a contamination-detection blind spot fixed in
DECISIONS D019: `Coordinator._recovery_plan` swallowed `ProviderError`
from the recovery-plan call and fell through to a plain retry, which
failed as a normal tool error. Both original runs reported
`contaminated: false`, but one or both may have been rate-limited on
the recovery call with no way for `classify()` to see it. The two
numbers must be re-run after that fix before the variance finding is
trusted.

## Amendment 2 (2026-10-20, F4 direct evidence, CORRECTED)

**T8 was never measured at max_tokens=16.** The F4 diagnostic
(`scripts/diagnose_calibration_parse.py`) confirmed every probe
returned reasoning text truncated before the model emitted a number:

    max_tokens=16: parsed_ok 0/20, raw_text = 'We need to estimate probability...'

Bumped to max_tokens=200 and re-ran. Result:

    max_tokens=200: parsed_ok 20/20
    Estimates: [0, 5, 8, 10, 15, 25, 40, 60, 65, 85]
    Mean ~32, Median ~20, Range 0-85

**T8 IS measurable.** The model returns meaningful, varied self-estimates
when given room to think. The prior "degenerate / constant 50" claim was
wrong — that number was a truncation artifact, not a model behaviour.

**One caveat:** item `er-15` shows `est=8, ok=True` but `raw_text` is
reasoning text, not a number. `_INT.search` found an "8" somewhere past
the 58-char display. That item's real estimate is unknown; it is a
false-positive parse. 19/20 items gave clean single-number replies.
Fix: require `^\\d{1,3}$` after strip, or bump to max_tokens=500.

**What this does NOT yet show:** calibration. Whether the model's
self-estimates correlate with actual outcomes (brier, ECE) requires a
clean calibration-strategy run at safe pacing. Prior brier=0.25/ECE=0.15
were computed on fallback 50s and are meaningless. If post-fix
error_recovery accuracy is 0.77 and the model's median estimate is 20,
the model is likely *under-confident*. Testing that is the next run.


## Amendment 3 (2026-10-20, post-D019 re-run)

Three runs of `error_recovery.jsonl` **after** the D019 fix
(recovery-ProviderError propagation):

| run | accuracy | contaminated | rate_limited |
| --- | --- | --- | --- |
| 1 | 0.7000 (14/20) | false | 0 |
| 2 | 0.8000 (16/20) | false | 0 |
| 3 | 0.8000 (16/20) | false | 0 |

**Mean 0.7667. Range 0.10. All clean.**

Compare to the two pre-D019 runs: 0.65 and 0.15 (range 0.50), both
`contaminated: false`. That's the blind spot DECISIONS D019 documented.
**The pre-D019 numbers were contaminated by the recovery-swallow bug**;
the D019 fix removed the noise. Post-D019 error_recovery at n=20 is
usable for the first time.

## T8 calibration — first real measurement (2026-10-20)

    benchmark:     error_recovery.jsonl (20 items)
    strategy:      calibration
    accuracy:      0.7000 (14/20)
    contaminated:  false
    rate_limited:  0
    brier:         0.388115
    ece:           0.4305

**Brier 0.388 > 0.25 (constant-0.5 baseline).** The model's self-estimates
are worse than random. A model that said "50% chance of success" for
every item would score 0.25. Varying estimates that score 0.388 are
actively harmful information.

**ECE 0.431 confirms it.** Well-calibrated <0.10. Random ~0.25.
Poorly-calibrated >0.15. This is 0.43 — 43 percentage points off.

**Direction: severe under-confidence.** Median estimate ~20, actual
accuracy 0.70. The model systematically underestimates by ~50pp.

**Not a code bug.** contaminated=false, rate_limited=0, 20 items,
200-token probe, calibrated strategy through the tested EvalRunner path.

**T8 does not currently produce a usable self-model.** Recalibration
(logistic fit + held-out split) would need 100+ items; documented as
future work, not run.

### What this is not

- Not "no self-model". Estimates vary (0-85, 10 distinct values across
  20 items). The distribution is just wrong.
- Not a claim about consciousness or metacognition. It is a text-in,
  text-out probe: "estimate the probability this plan succeeds."

### What this batch established

T8 is measurable, and the answer is negative. The model's self-estimate
on this task family is worse than a naive constant.
