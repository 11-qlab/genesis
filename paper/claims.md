# Honest claims — cite these, not the per-script prints

## Cross-family (model evidence in taxonomy.json)

**3/3 classes** confirmed across ≥2 model families.
Classes: `prior_override_failure/function_name_trigger`, `prior_override_failure/stochastic`, `prior_override_failure/systematic`

## Grounded (execution-verifiable, anchor-verified)

**3/3 classes** have ≥1 template that discriminates known-correct from baseline under `_known_correct_for` / `_baseline_for`.
Classes: `prior_override_failure/function_name_trigger`, `prior_override_failure/stochastic`, `prior_override_failure/systematic`

**3/9 anchors discriminate.** The 6 TOO_STRICT anchors have 3 root causes (impl_missing_name ×3, signature_mismatch ×2, wrong_output ×1); the dominant cause is the oracle's per-class (not per-template) reference implementation, not test bugs. See `state/toostrict_breakdown.jsonl`.

## Anomalies (unexplained failures, honest frontier)

- `unclassified_class`: 3
- `skip_generation_failed`: 1
- `skip_no_plan`: 1
- `candidate_invalid`: 1
- `contaminated_run`: 1

After excluding 3 harness-class records (`test_gap_for_generation`), the real anomaly count is **4** — each one a place the loop stopped because it couldn't validate. That refusal IS the contribution.

## What the 2026 survey says, and what this work adds

> The survey: *no LLM-era system demonstrates an externally validated in-loop oracle.*

Genesis: **3/3 classes** have an in-loop execution-verifiable oracle (known-correct vs baseline). This falsifies the survey claim **for the subset measured here**. It does not falsify it for the field: the oracle is limited to classes with a hand-authored reference impl (3 in this work), and each class is grounded by exactly one discriminating anchor. See limitation 4. Boundary is stated, measured, and reproducible via `./run_paper.sh`.

## Limitations (paper §5, verbatim)

1. `_known_correct_for(cls, cand)` returns one impl per class. This is why 6/9 anchors cannot discriminate — the test template and the reference impl disagree on name/signature. Per-template reference impls would close this gap but require hand-authoring (the human bottleneck the gate exposes).
2. Sandbox is `subprocess.run(-I)` with stripped env and 5s timeout. Stops accidents, not adversaries. RestrictedPython/container is the upgrade.
3. `test_gap_for_generation` has no `_known_correct_for` impl → cannot be grounded in this pipeline. It is a harness class, reported honestly as an anomaly.

4. **The discriminator is a floor, not a ceiling.** A template is declared
   discriminating iff it (a) passes against `_known_correct_for` and (b) fails
   against `_baseline_for`, which is `def f(*a, **k): return None`. This proves
   the test *rejects a null stub*. It does NOT prove the test captures the class
   semantics — `assert f(4) == 2.0` discriminates against `return None` and also
   passes many wrong implementations. Groundedness here means "rejects garbage,"
   not "uniquely identifies the correct answer." Raising this floor requires
   adversarial anchors (ACE-style), which this work does not attempt.

5. Each grounded class rests on **exactly one** discriminating anchor
   (3/9 total). Single-anchor support is thin. Reporting the count is the honest
   alternative to a false confidence interval.
