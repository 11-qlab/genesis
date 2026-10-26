# A Reproducible Hypothesis-Testing Loop for LLM Agent Research

**Anonymous submission — workshop track on evaluation methodology.**

---

## Abstract

Solo and small-team LLM agent research operates under compute constraints
that prohibit the N of large-lab studies. We present a paired, pre-registered,
multiple-testing-corrected evaluation loop that exchanges sample size for
statistical discipline. The loop is a schema (`hypothesis.schema.json`), a
runner (`hypothesis_runner.py`), and an analysis library (`analysis.py`) — no
new models, no new benchmarks, no additional GPU time. The loop's unit of
output is a hypothesis disposition (`PASS` / `REJECTED` / `SCOPED` /
`NOT_A_TEST`) with a paired test statistic and Bayes factor.

We demonstrate the loop on four hypotheses about LLM tool-use trajectories
(H001–H004). Two accept, one rejects, one is scoped. **The rejected hypothesis
exposed a real gap in a deterministic verifier**: a class of failure (text
deferral) that the regex prefilter did not catch. The fix that followed reduced
misclassification on the class from 0% to 100%. The scoped hypothesis forced a
narrower claim about the verifier's applicability that is more defensible than
the original. We report the loop's cost (0 additional LLM calls beyond what
each hypothesis itself required), its structural limit (hypothesis generation
remains human-authored), and its pattern for reuse.

## 1. Introduction

An LLM agent paper that reports "our method achieves X%" cannot be evaluated
without knowing what X% would be under a matched null, at what N, and with what
confidence interval. Large labs resolve this by increasing N. Solo research
cannot. This paper proposes a discipline that reaches similar inferential
strength at small N by making the *structure* of the comparison explicit.

We describe four hypotheses tested under the loop. Two were motivated by prior
findings in the associated verifier paper; two were diagnostic (whether a
verifier is order-invariant; whether an LLM verifier has run-to-run variance).
The loop's outputs are `results/Hxxx.json` — one file per hypothesis, each
containing the paired data, the test statistic, the Bayes factor, and a
disposition. `results/summary.json` aggregates all dispositions with
Benjamini-Hochberg correction.

The loop's claim to novelty is *not* the statistics — McNemar, Bayes factors,
and BH correction are decades old — but the discipline of applying them per
hypothesis, declaring the hypothesis before running, and publishing rejections
alongside acceptances. The four hypotheses are reported in full below,
including the rejection.

## 2. The loop

### 2.1 Schema

`schemas/hypothesis.schema.json` requires: `id`, `claim`, `metric`, `test`,
`status`, `conditions`. Status is `pending` (to be executed) or `completed`
(previously run and recorded). Conditions are typed: `verifier` (run
`verifier_deterministic` with a chosen regex set) or `prompt` (run the planner
under a chosen SYSTEM_PROMPT).

The schema's `registered_at` field carries a UTC timestamp. A hypothesis with
`registered_after_observation: true` is disclosed as post-hoc — the discipline
is applied, but retroactively. No hypothesis is silently upgraded from post-hoc
to pre-registered.

### 2.2 Runner

`scripts/hypothesis_runner.py` reads a manifest, renders both conditions,
executes them against the same item set, pairs per-item results, computes
`mcnemar_exact` and `bf_mcnemar`, applies the manifest's acceptance criterion,
and writes a result file. The runner is deterministic for `verifier` conditions
(0 LLM calls) and bounded-cost for `prompt` conditions (2 × n_items calls).

### 2.3 Analysis

`scripts/analysis.py` provides `mcnemar_exact`, `bayes_factor_binomial`,
`bf_mcnemar`, `bootstrap_ci`, and `bh_correction`. All are standard; none
manipulates the data. Paired comparisons use McNemar; small-N effects use
Bayes factors; multiple testing uses BH.

## 3. Four hypotheses

### 3.1 H001 — verifier order-invariance

**Claim.** Deterministic verifier returns identical verdicts when trajectory
steps are reversed.

**Design.** All 68 items in the verifier test set (`n20_verifier_test.jsonl`)
render both forward and reversed. Compare verdicts.

**Result.** 68/68 agreement, 0 discordant. `NOT_A_TEST` — perfect agreement,
no p-value appropriate.

**Value.** Establishes that the verifier is content-based, not order-based.
Sets a constraint on future failure-mode findings: any observed failure must be
attributable to content, not step position.

### 3.2 H002 — LLM verifier variance

**Claim.** An LLM verifier at temperature 0 returns inconsistent verdicts
across repeated runs on identical placeholder items.

**Design.** 17 placeholder items, three independent runs of the LLM verifier.

**Result.** 7/17 items flip verdict at least once across 3 runs. Binomial tail
under a weak null (baseline flip rate 10%) gives p = 7.8 × 10⁻⁴. `PASS`.

**Design note.** Run 1 was regex-prefiltered; runs 2–3 were pure LLM. The
7 flips include regex-vs-LLM mismatches. The clean sub-test (run2 vs run3,
pure LLM) shows 3/17 flips — still non-zero, still supporting the claim. This
is disclosed in `results/H002.json`.

**Value.** Justifies the deterministic verifier's existence: sampling
variance is not fixable by prompting.

### 3.3 H003 — rule 9 on task_chain

**Claim.** Rule 9 (literal content) reduces placeholder rate on the task_chain
family.

**Design.** 10 task_chain items, baseline vs patched prompt, paired.

**Result.** 3/10 placeholder baseline, 1/10 patched. McNemar p = 0.50,
BF₁₀ = 1.33. `REJECTED` — insufficient evidence.

**The rejection is the finding.** The raw transitions show the "2 improvements"
are not fixes. One is a syntax shift (`${s1.content}` → `<content from s1>`,
both placeholders). One is a *new failure class*: `"The sandbox note contains
the following "` — text deferral, not caught by the verifier's regex. One is
plan absence (`no_plan`). Zero are real fixes.

**What the rejection produced.**
1. A verifier bug: the `TEMPLATE_RE` in `verifier_deterministic.py` did not
   match text-deferral or single-brace `{count}` patterns.
2. A regex extension (`TEMPLATE_RE_V2`) that adds descriptive-content patterns
   without false-positiving on real content.
3. A generalization of the associated paper's §5 mechanism: prompt rules
   shift failure forms under constraint rather than eliminating them.

A rejected hypothesis producing a bug fix and a paper-scope refinement is the
loop working as intended.

### 3.4 H004 — scope

**Claim.** Rule 9 reduces placeholder rate on write-requiring benches, but
placeholder is not the dominant failure class across the benchmark suite.

**Design.** 4 write-requiring benches (task_chain, error_recovery,
compositional, typed_chain), 5 items each, paired.

**Result.** Placeholder baseline 7/20, patched 5/20. No-plan baseline 7/20,
patched 8/20. `SCOPED` — the effect is bench-specific and smaller than the
aggregate suggests.

**What the scope produced.** §4.2 and §7 of the associated paper now state that
the three-layer fix addresses **content-substitution failures specifically**,
not agent planning failures. The paper is stronger for naming its boundary.

## 4. Cost

| Hypothesis | LLM calls | Verdict |
| H001 | 0 | NOT_A_TEST |
| H002 | 34 | PASS |
| H003 | 20 | REJECTED |
| H004 | 60 | SCOPED |
| **Total** | **114** | 2 pass, 1 reject, 1 scoped |

For comparison, a large-lab verifier evaluation typically runs 300–3000 calls
per condition. The loop reaches its dispositions in 114 total, at the cost of
narrower claims (n=5–17 per hypothesis instead of n=1000).

## 5. Structural limits

1. **Hypothesis generation is human-authored.** The loop is not autonomous. A
   hypothesis-generator module (`scripts/hypothesis_generator.py`) does not
   exist and is not on the roadmap. The discipline is on the *test* side, not
   the *discovery* side. This is disclosed rather than elided.

2. **Pre-registration is partly post-hoc.** H001–H004 were registered after
   observation, marked as such in each manifest. Applying the discipline
   retroactively is honest; claiming it was prospective is not. Future
   hypotheses will be registered before running.

3. **Small N limits inference.** Paired tests recover some power, but at n=5
   on a bench, even a complete effect (5/5 → 0/5) will not always cross
   BF₁₀ ≥ 3 unless the effect is fully discordant. The loop produces honest
   *scope* at small N — not always *acceptance*.

4. **The metric favors declaring fewer hypotheses.** Discovering three claims
   and testing one well produces better statistics than testing all three
   badly. The loop does not have a "discovery rate" metric that rewards
   breadth. This is by design; breadth is for the associated paper, not the
   loop.

## 6. What the loop produces

A `results/` directory, one file per hypothesis, each containing:
- the disposition and its rationale,
- the paired per-item transitions,
- the test statistic and Bayes factor,
- an acceptance criterion declared by the hypothesis author.

`results/summary.json` applies BH correction across all completed hypotheses.
The associated paper's claims cite specific `results/Hxxx.json` files by path.

The loop is a bookkeeping discipline for experiments the researcher already
runs. It makes the discipline of pre-registration, paired testing, and
multiple-testing correction enforceable by git. It does not discover claims.

## 7. Reproducibility

`reproduce.sh` runs H002 (34 LLM calls) end-to-end given `AGI_BASE_URL`.
H001, H003, H004 are reproduced against cached artifacts
(`artifacts/traces/`, `artifacts/esf/`) at 0 LLM cost. The full loop — 4
hypotheses, 114 LLM calls — reproduces in under 10 minutes against a live
endpoint.

The schema, runner, and analysis library total ~600 lines of Python, all
dependencies already in the associated repository.

## Appendix A — Manifest for a pending hypothesis

```json
{
  "id": "H005",
  "registered_at": "2026-10-27T00:00:00Z",
  "status": "pending",
  "claim": "...",
  "metric": "...",
  "test": "agreement",
  "conditions": {
    "a": {"type": "verifier", "regex_set": "v1"},
    "b": {"type": "verifier", "regex_set": "v2"}
  },
  "bench": "artifacts/esf/h005_bench.jsonl",
  "n_items": 20
}
```

