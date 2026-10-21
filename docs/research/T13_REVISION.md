# T13 — Plan revision

**What it is:** when the current plan has failed (step-level retry
exhausted), throw it out and ask the model for a complete new plan given
the original goal, the failing step, and the error. Execute the new
plan. Allow up to `max_revisions` total attempts.

**Why it might help:** the current `Coordinator` can only retry a failed
step. If the whole approach is wrong (e.g., the model chose `fs_read` for
a goal that needs `fs_list`), no number of step retries fixes that.
Plan revision gives the model a second look at the goal with concrete
failure signal.

**Why it might not help:** if the model is fundamentally miscalibrated
about a goal, it may produce the same wrong plan twice. The revision
prompt makes the failure explicit but doesn't change the model's
knowledge.

## Measurement protocol

`scripts/measure_revision.py` runs `task_chain.jsonl` (20 items) through
two conditions:

1. **baseline**: `Coordinator.execute(goal)` — step-level retry only
2. **revision**: `RevisionAgent(goal, max_revisions=1)` — one plan
   revision allowed

Reports per-condition accuracy. The delta is the number of items that
revision recovered that baseline did not.

## What this measures

Whether bounded plan revision (n=1) improves accuracy on `task_chain` at
n=20.

## What this does not measure

- Whether revision generalizes beyond `task_chain`
- Whether 2+ revisions help (would need a separate run)
- Whether the revised plan is "better" in any abstract sense — only
  whether it succeeds where the original failed
- Anything about AGI

## Cost

Each item is 1-3x the model calls of baseline (initial plan + recovery
+ retry + potentially one revised plan + its execution). At n=20 and
2s pacing, ~20-30 minutes.

## Honest framing

There is no known path to AGI. This trajectory does not claim to be one.
It measures one specific technique — bounded plan revision — that the
project's own `AGI_REQUIREMENTS.md` names as missing. Building it and
measuring it is one honest step. It does not close the AGI gap.

## Result — multi-run T13-basic vs same-session greedy (2026-10-20)

Same session, same benchmark (`error_recovery.jsonl`, 20 items), same
9-key pool, same pacing (5000ms), all runs `contaminated: false` and
`rate_limited: 0`.

| condition | runs | mean | range | low | high |
| --- | --- | --- | --- | --- | --- |
| greedy | 0.75, 0.80, 0.80 | **0.7833** | 0.05 | 0.75 | 0.80 |
| T13-basic (2 attempts) | 0.80, 0.85, 0.90, 0.95 | **0.8750** | 0.15 | 0.80 | 0.95 |

**Delta: +0.0917 (≈ +1.8 items on average).**

### Distribution shape

- Greedy: 3 samples, tight 0.75–0.80.
- T13-basic: 4 samples, wider 0.80–0.95.
- Overlap: one point (basic min 0.80 == greedy max 0.80). Every other
  basic run is strictly above every greedy run.

### Honest verdict

**Weak positive signal, below the noise band.** Delta 0.09 < the 0.15
threshold from `bench/README.md`. Three of four basic runs exceed every
greedy run, which is suggestive, but n=3 vs n=4 is too small for a
claim. To make it a real measurement needs 2+ more runs of each, or a
larger benchmark (n=20 is the ceiling for the current file).

### Correction to the prior single-run T13 claim

The prior note in this doc said "+2 items over greedy 0.70" based on
one T13-basic run at 16/20. Both numbers were wrong for a comparison:

- **Wrong baseline.** Greedy was 0.70 in an earlier session at
  2000ms pacing, not the same-session 0.7833 at 5000ms pacing.
  Cross-session comparison is what `bench/README.md` explicitly forbids.
- **Wrong point estimate.** The 16/20 = 0.80 T13-basic run was the *low
  end* of the actual distribution. The mean is 0.875, not 0.80.

The corrected claim is: **T13-basic mean +0.09 over same-session greedy
on error_recovery, distributions nearly disjoint, sample too small for
a claim.** That's a weaker claim than the single-run version and a
stronger one than "delta = 0" — which was the T13 result on task_chain.
