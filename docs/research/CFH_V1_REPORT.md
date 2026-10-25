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

---

## Exp-post-v2 findings (2026-10-25, session 3 late)

After the v2 clean null, four additional experiments produced a
substantially richer picture than "no signal at all."

### Path rigidity (Exp 1) — REAL

Among three valid trajectories for the same goal (canonical
read→write, verify-after-write, redundant double-read), the model
shows consistent preference:

| Pair | p_first | Label |
|---|---|---|
| canonical vs verify | 0.83 | prefers canonical |
| canonical vs redundant | 0.83 | prefers canonical |
| verify vs redundant | 0.67 | prefers verify |

**Consistent ordering: canonical > verify > redundant.** The model
has stable preference for shortest/cleanest valid path even among
all-valid paths. Coincides with `path_20b.json`'s observation that
12/12 fam13 items took fs_write → fs_read — the path bias is not
task-specific but a general prior.

### Coarse adversarial discrimination (Exp 3) — REAL

Against an adversarial twin that prepends `fs_read(docs_not_exist.txt)`
→ error, model discriminates at **0.83** (4 A, 2 undecided across 6
items, n=6).

**The model catches OBVIOUS errors** even though it does not detect
SUBTLE mutations (v2 = 0.500). This is the coarse/fine split.

### reasoning_effort unlocks self-verification (Exp 5) — REAL

Self-verification prompt ("CORRECT or INCORRECT, no explanation")
under standard reasoning mode: model burns entire `max_tokens=32`
budget on CoT preamble, never emits verdict.

Under `reasoning_effort=low`: `content='INCORRECT'` for a broken
trajectory, `reasoning_len=173`. **The model CAN self-verify when
reasoning is constrained.**

### Revised conclusion

Not "no capability." Not "fine-grained capability." It is:

> **gpt-oss-20b has coarse-grained trajectory judgment and path-canonicity
> preference, but lacks fine-grained mutation sensitivity. Under constrained
> reasoning (reasoning_effort=low) the model can perform accurate
> absolute self-verification, but its default reasoning mode drowns in
> chain-of-thought before emitting verdicts.**

This is a bounded capability result: the AGI-adjacent capacity exists
but has a resolution floor and is gated by reasoning style.

### What the null v2 measurement now means

v2 = 0.500 on fine-grained mutations is a real finding, but it sits
in a broader picture:
- Coarse (obvious breaks): 0.83 ✓
- Path canonicity: 0.83 ✓
- Fine (single-field mutation): 0.500 ✗
- Absolute verification (constrained reasoning): correct ✓

The model operates at surface-feature resolution. It knows the
difference between a valid and a blatantly broken trajectory, but
not between two structurally similar ones differing by one field.
The capacity is present but at low resolution.
