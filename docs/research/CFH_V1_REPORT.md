# Counterfactual Hull Probe (cfh) — v1/v2 results

**Status:** clean null, documented 2026-10-25
**Model:** gpt-oss-20b · **Families:** fam14in, fam14out

## Summary
Probe measured whether gpt-oss-20b distinguishes correct tool-use
trajectories from near-miss twins. v1 (tool-name-only) = 0.833 on
fam14in, 3 confounds ruled out. v2 (full trajectories with
observations) = 0.500, CI [0.406, 0.594]. v1 was a rendering artifact:
empty-arg trajectories look like stubs, so any mutation that adds
structure made the twin look more real.

## v1 result (run 20261024-200026)
| Family | Disc. | 95% CI | n |
|---|---|---|---|
| fam14in | 0.833 | [0.625, 1.000] | 12 |
| fam14out | 0.500 | [0.250, 0.750] | 8 |

samples=3 confirmation: 1.000 (6/6).
Confounds ruled out: position bias (1A/2B/3U identical-vs-identical),
junk-arg (swap_tool 0.75, reorder 1.00 with no arg diffs), length prior
(mean 0.38, mostly undecided on alternate-valid).

## v2 result (16 successes, k=2)
| Family | Disc. | 95% CI | n |
|---|---|---|---|
| fam14in | 0.500 | [0.375, 0.625] | 24 |
| fam14out | 0.500 | [0.312, 0.688] | 8 |
| overall | 0.500 | [0.406, 0.594] | 32 |

## Why the two disagree
v1 rendered as fs_read({"path":""}) → fs_write({"path":""}).
HallucinateField added {"timeout_ms":true}, making the twin look MORE
like a real trajectory. The model preferred visible structure, not
correctness. v2 matched rendering; discrimination collapsed.

## What this means
Under controlled rendering, gpt-oss-20b does not discriminate
trajectory soundness on fam14. Combined with the hull refutation
(12/12 fam14out items pass at least once across two runs):
**no measurable AGI-adjacent capacity on fam14 at 20B tier.**

## Open (v3)
- SwapArgument no-op (args empty in checkpoint)
- n=32 too small; weak signal 0.55 needs n≥100
- 60% undecided rate — grammar-constrained probe would help
- Other families (fam11, fam13) unprobed
- Larger models unprobed

## Reproduce
    scripts/infra_up "<colab-url>"
    scripts/run_experiment fam14in fam14out
    scripts/probe artifacts/runs/<ts> --k 2 --samples 1

## Honest accounting
Three sessions: 5 harness bugs fixed, 2 candidate signals found,
2 refuted, 1 clean null, infrastructure to keep measuring.
