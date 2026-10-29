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

