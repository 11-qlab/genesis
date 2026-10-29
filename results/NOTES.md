# Session findings — keep this file alongside the data

## Confirmed
- D02 failure on gpt-oss-120b natural baseline: reformatting, not substitution
- Hardening prompt with "character-for-character" fixes it (10/10)
- qwen3.8-27b D baseline non-deterministic: 6/10 in one run, 6/10 in another, but 2 vs 4 errors
- allam-2-7b hallucinates generic content ("This is the content to be written in the file")

## Design decision (record the reason)
- Baseline = natural prompt (no copy instruction)
- Prompt_patch = natural + explicit character-for-character copy
- Executor_patch = mechanical substitution
This isolates the question "does prompt compliance fix substitution failure?"

## Harness bugs hit (all documented, all fixed)
1. cfh.tools.dispatch not bound
2. Wrong API endpoint (OpenAI instead of Groq)
3. Argument replacement instead of merge
4. Stale prompt name after rename
5. Placeholder counter missed hallucinated substitutions
6. Success check compared content only, not path
7. llama-3.1-8b-instant not actually on account (all earlier "llama" rows were qwen)

## ⚠️ ANOMALY — prompt_patch errors on weaker models (2026-10-29)

Full 3-model grid revealed unexpected prompt_patch behavior:

| Model | C baseline | C prompt_patch | C exec | D baseline | D prompt_patch | D exec |
|---|---|---|---|---|---|---|
| gpt-oss-120b | 10/10 | 10/10 | 10/10 | 9/10 | 10/10 | 10/10 |
| qwen3.8-27b | 10/10 | **2/10 (8 err)** | 10/10 | 6/10 (2 err) | 8/10 (2 err) | 10/10 |
| allam-2-7b | 0/10 | **1/10 (9 err)** | 10/10 | 0/10 | 6/10 (4 err) | 10/10 |

qwen C prompt_patch (2/10) is WORSE than its baseline (10/10).
allam C prompt_patch has 9 errors where baseline had 0.

Most likely cause: the hardened prompt's `<OBSERVATION>...</OBSERVATION>`
tags are echoed into the model's JSON output by weaker models, or the
longer prompt pushes them past a length where `json_object` mode stops
working reliably. Not yet diagnosed.

Interpretation limit: the prompt_patch rows must NOT be read as evidence
for or against "prompt compliance fixes substitution." They measure
"can the model follow a longer prompt without breaking JSON output,"
which is a different question.

The gpt-oss-120b prompt_patch rows ARE valid — same instruction, no
errors, expected behavior. The qwen and allam prompt_patch rows are
contaminated by an undiagnosed prompt-shape interaction.

Action: diagnose one qwen C prompt_patch error and one allam C prompt_patch
error before the next statistical claim.

---

## CORRECTION (2026-10-30) — supersedes the anomaly note above

The prompt_patch errors described in the section above (qwen-C 8 err,
allam-C 9 err) were **not** caused by `<OBSERVATION>` tags breaking JSON.
That diagnosis was wrong.

### Actual cause: harness bug #8 (incomplete fix of bug #3)

The merge block read:

    for k, v in produced.get("args", {}).items():
        args[k] = v

This lets the model override **any** arg it returns, including `path`.
When the harder prompt caused the model to include a `path` field in its
response (e.g. `"."`, `"path/to/file"`), the model's path replaced the
ground-truth path and `_fs_write` raised `IsADirectoryError`.

### Fix

    for k, v in produced.get("args", {}).items():
        if k == key:
            args[k] = v

Model controls only the substitution argument; every other arg is ground
truth from the task dict.

### Effect of the fix (grid re-run with `if k == key`)

| Model | C base | C pp | C exec | D base | D pp | D exec |
|---|---|---|---|---|---|---|
| gpt-oss-120b | 10/10 | 10/10 | 10/10 | 9/10 | 10/10 | 10/10 |
| qwen3.8-27b | [fill] | [fill] | 10/10 | [fill] | [fill] | 10/10 |
| allam-2-7b   | 0/10 | **10/10** | 10/10 | 0/10 | **10/10** | 10/10 |

The allam result is the sharpest: baseline 0/10 both families,
prompt_patch 10/10 both families. Complete prompt-fixability at 7B
once the harness stops letting the model corrupt non-substitution args.

### qwen3.8-27b variance across identical runs

Same code, same prompt, same tasks, `temperature=0`, `seed=42`:

| run | C baseline |
|---|---|
| 1 | 10/10 (0 err) |
| 2 |  9/10 (1 err) |
| 3 | 10/10 (0 err) |
| 4 |  5/10 (5 err) |
| 5 | [current re-run] |

The variance is ~50 percentage points on identical inputs. This is a
property of qwen3.8-27b / Groq at 27B, not the harness. Any single-run
qwen number must be reported as a sample from this distribution.

### Bug #8 — methodology lesson

    Stage          Code                                            Blast radius
    Bug #3         args = produced["args"]                         all args
    "Fix" for #3   for k,v in produced["args"].items(): args[k]=v  any arg
    Bug #8 fix     if k == key: args[k] = v                        substitution only

The "fix" for bug #3 reduced the blast radius from all-args to any-arg.
The report showed errors=40 → errors=0, so the bug appeared fixed. The
underlying defect (harness trusts model-controlled args) survived,
hidden, until a prompt change caused the model to return an extra arg.

**Incremental fixes can hide a defect without eliminating it.** A fix
that reduces blast radius is not a fix that eliminates the defect. The
only protection is asserting the invariant directly: the model controls
only the substitution argument.


---

## CORRECTION 2 (2026-10-30) — commit f1b08f1 contains mixed data

`f1b08f1` reported n=20 per condition because `run_family.py` opened
`--out` in append mode. `git checkout HEAD -- results/` restored the
old buggy files, then the re-run appended to them. Each `runs_*.jsonl`
contained 10 pre-fix + 10 post-fix records mixed together.

Effect: `report_*.md` showed averages of pre-fix and post-fix data, not
the post-fix result. Specifically:

  allam C prompt_patch: reported 11/20 (55%)  →  new-fix only: 10/10
  allam D prompt_patch: reported 16/20 (80%)  →  new-fix only: 10/10
  qwen  C prompt_patch: reported 12/20 (60%)  →  new-fix only: 10/10

McNemar was inconsistent with report.py: it pairs by (family, task_id),
and with two records per key the dict overwrite kept only the last
(new) entry. So report.py showed mixed averages while mcnemar.py
analyzed new data only — internal contradiction.

Fix: run_family.py now truncates `--out` by default and requires explicit
`--append` for the 2nd+ writes in a grid run. Full grid re-run in
this correction commit. Files now contain 60 records per model, 10 per
condition, single-run.

Lesson: a file write whose mode ("a" vs "w") depends on caller context
is a footgun. Every tool that writes a named file should default to
truncate and require an explicit flag to append. The mixed n=20 output
is what happens when the default is the less-safe option.

---

## Bug #10 — regression from over-hardening (2026-10-30)

The path-invariant assertion added to prevent bug #8 regression turned
out to be too strict: it fired on any model response that included a
`path` key, even though the `if k == key` guard already dropped that
value before it reached the task args. Result: every baseline and
prompt_patch call raised AssertionError; every executor call passed.
The reported grid for gpt-oss was 0/10 / 0/10 / 10/10 with 10 errors
in every baseline cell — a false deflation that looked like a
model-capability failure.

Fix: removed the assert. The correct regression guard is not "model
never returned path" (model behavior we don't control); it's "harness
never assigned model's path to task args" (harness behavior we do
control), and the `if k == key` guard already enforces that.

The on-disk content verification (read the file back after fs_write,
compare to prior_obs) is retained.

Lesson (same shape as bug #8): an incremental fix that tightens a
guard can over-tighten it and break the working case. The invariant to
assert is the one the code enforces, not a stricter property the model
happens to satisfy.

This is the 10th harness bug found in one session, and the second
introduced by a fix for an earlier bug. The pattern is stable: fixes
need to be scoped to the actual defect, not to the general area.

---

## Bug #11 — merge loop lost by drop_assert.py (2026-10-30)

The drop_assert.py patch (fixing bug #10) replaced the assert block with
9 lines of comments but deleted the merge loop itself. The
`for k, v in produced...` / `if k == key` / `args[k] = v` lines vanished.

Signature if auth had been working: baseline/prompt_patch cells would
have shown success=False, placeholders=1, errors=0 (placeholder written
to disk; on-disk check compared placeholder to prior_obs and failed).
Auth was broken first, so the audit saw AuthenticationError 401 x 10,
which presented as errors=10 — masking bug #11 behind bug #12 (auth).

Restored in the commit that supersedes this note. The merge loop now
sits between `produced = call_model(...)` and `out = dispatch(...)` with
clean two-line comment and no assert.

## Audit result (2026-10-30) — the answer to "94.3% → 65.5%"

verify_100.py replayed every claimed-100% cell from commit 8fd4161:
14 cells × 3 repeats = 42 runs.

Result: 14/14 VERIFIED at 30/30. 0/14 INFLATED.

The 100% claims in the committed grid survive independent replay. The
paper's "harness inflates, audit reveals lower" pattern did not apply
here. The interim INFLATED verdicts (2 cells, then 8 cells) were harness
bugs #10 and #11 respectively, not claim inflation.

The 4 sub-100% cells (gpt-oss D baseline 9/10, qwen D baseline 6/10,
allam C/D baseline 0/10) are already documented above as variance-prone
samples, not point estimates. The audit did not cover them because
verify_100.py audits only claimed-100% cells by design.

## Fix-chain hazard — the methodology finding

| Bug | Introduced by | Caught by |
|-----|---------------|-----------|
| #3  | original code | manual review |
| #8  | fix for #3    | commit-message inconsistency (10/10 vs 55%) |
| #10 | fix for #8    | full grid re-run showed 0/10 |
| #11 | fix for #10   | independent replay (verify_100.py) |

Five bugs in one session. Two introduced by fixes for earlier bugs (#10,
#11). Both caught only by out-of-band checks — the diff looked correct,
the file parsed, report.py and mcnemar.py produced numbers. Only
verify_100.py, a separate mechanism that re-verifies the claim from
scratch, caught them.

**Incremental fixes introduce defects faster than manual review catches
them.** A fix that appears correct in the diff can silently delete code
(bug #11), tighten a guard past its scope (bug #10), or reduce blast
radius without eliminating a defect (bug #8). The only reliable detector
is an independent mechanism that re-verifies the claim from scratch,
not a re-read of the diff and not a re-run of in-band tests.

For agent benchmark work, this suggests: every claim in a benchmark
report should be accompanied by an audit script that independently
regenerates it. `verify_100.py` is 60 lines. The reason most agent
benchmark results are trusted is that nobody runs an equivalent.
