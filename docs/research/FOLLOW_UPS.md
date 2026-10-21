# Follow-ups from T2/T8/T9 measurement session

Three items that would turn the four raw numbers into real findings.
Each is a small amount of code and a small amount of compute.

## F1 — extract the baseline/novel split from T9

The `run_bench` helper in `scripts/measure_with_keys.sh` (and the one in
step50) calls `agi eval run` and reads the aggregate accuracy. The
`compositional.jsonl` items have `novel_ordering` tags (0 for baseline,
1 for novel). Extract per-tag accuracy from the report JSON.

Where to implement: a small utility in `src/agi/evaluation/splits.py` that
takes a `Dataset` and an `EvalResult` and returns a `dict[tag_value,
(passed, total)]`. Then a `--split-by` flag on `agi eval run` that prints
per-split accuracy in the summary.

Run cost: no new model calls. Reads the existing report.

## F2 — multi-run mean for T2 self-consistency

The +0.05 delta (0.95 vs 0.90) is one run each. `bench/README.md` says
multi-run mean is required for a point estimate. Run greedy and
self-consistent 3–5 times each, compute mean + range, check whether the
delta survives.

Run cost: 4 extra runs × 20 items × ~3s/call = ~10 min at 2000 ms pacing
with 9 keys. Feasible.

## F3 — confirm the T8 constant-0.5 hypothesis

The brier=0.25 + ece=0.10 combination is arithmetically consistent with
a model that returns constant 50% for every probe. Confirm or refute by
dumping the per-item `calibration_estimate` field.

Implementation: `scripts/dump_calibration_estimates.sh` that runs
`agi eval run --strategy calibration` and prints each item's estimate
alongside its outcome.

If the estimates are all 50: T8 finding is "the model does not estimate."
Record and move on. The prompt-tuning escape is a documented
`AGI_REQUIREMENTS.md` item (capability self-model) that this trajectory
does not solve.

If the estimates vary: brier 0.25 is a genuine estimate that happens to
average to 0.25, and T8 has weak-but-real content. Then run 3–5 more
times to characterize the mean.

Run cost: one run, no new model calls beyond the calibration probe
itself.

## F4 — distinguish "model returns 50" from "probe fallback returns 50"

**Why:** every item gets `calibration_estimate=50`, but that's the
symptom of two causes: the model truly returns 50, or
`_INT.search()` fails and `CalibrationProbe.estimate`'s `return 50`
fallback fires.

**How:** `scripts/diagnose_calibration_parse.py` runs the probe directly
per item and prints `raw_text` and `parsed_ok`. See
`scripts/diagnose_calibration_parse.sh` for the wrapper.

**Run cost:** one error_recovery pass at n=20 (~40 model calls).

## F5 — a usable error_recovery measurement

**Why:** two clean runs gave 0.65 and 0.15. Range 0.50.

**Options:** multi-run mean (5 runs) OR grow the benchmark to 100 items
OR stratify by error type. Cost: 100 items × 5 runs × ~2s/call = ~17 min
with the 9-key pool.
