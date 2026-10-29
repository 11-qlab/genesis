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
