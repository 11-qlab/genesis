# Differential name-contrast oracle

## Purpose

The classical pipeline grounds `prior_override_failure/function_name_trigger`
using a hand-authored reference implementation (`_known_correct_for`). That
implementation returns one function body per class. A generated test that calls
the function by a different name fails to grade, producing a `capability_limit`
verdict (`state/candidate_verdicts.jsonl`).

This report tests a different oracle type that **does not need a reference
implementation**: hold the spec and input fixed, change the function name, and
compare the model's output after normalizing the name. If the model's behavior
changes, the model is name-sensitive. If not, it is name-invariant.

That is a *different claim* than "the template discriminates." It grounds
"the model is name-triggered" without needing to know the correct answer.

## Method

**Contrasts (3):**

| ID | Name A | Name B | Structural relationship |
|---|---|---|---|
| D001 | `binary_search` | `find_index` | Same algorithm, different label |
| D002 | `binary_search` | `min_heap` | **Different algorithm** |
| D003 | `find_index` | `smallest_k` | Same algorithm, different label |

**Spec (fixed):** "Return the index of the first occurrence of x in sorted arr."

**Inputs (3):** `[[1,2,2,3], 2]`, `[[], 1]`, `[[1], 1]`.

**Models (2, cross-family):**

- `openai/gpt-oss-20b` — gpt-oss family
- `qwen/qwen3.8-27b` — qwen family

**Calls:** 3 contrasts × 3 inputs × 2 names × 2 models = **36 calls**.

**Rule per (model, contrast):**

- `NOT_EXECUTED` — all 3 inputs failed at the API → infra, not a result
- `NAME_INVARIANT` — every executed input is identical after rename → model is name-blind
- `GROUNDED` — majority of executed inputs differ after rename → model is name-sensitive

**Preflight:** before any contrast, `80_minimal_differential.py` hits
`/v1/models` and refuses to run if either model ID is absent from the account.
That catches retired model IDs before 36 calls are spent on 404s.

## Results

From `state/minimal_differential.jsonl` (single run, 2026-10-29):

| Model | Grounded | Name-invariant | Not executed |
|---|---|---|---|
| `groq_gpt_oss_20b` | **3/3** | 0/3 | 0/3 |
| `groq_qwen_38_27b` | **1/3** | 2/3 | 0/3 |

**Per-contrast breakdown:**

| Model | D001 (bs vs find) | D002 (bs vs heap) | D003 (find vs small) |
|---|---|---|---|
| gpt-oss-20b | GROUNDED 3/3 | GROUNDED 3/3 | GROUNDED 2/3 |
| qwen3.8-27b | NAME_INVARIANT 0/3 | **GROUNDED 3/3** | NAME_INVARIANT 0/3 |

## Finding

**The mechanism is family-and-contrast dependent, not universal.**

- `gpt-oss-20b` is name-sensitive on every contrast, including within-family
  variants (`binary_search` vs `find_index`). The name token itself triggers a
  different canonical prior.
- `qwen3.8-27b` is name-sensitive **only** on `binary_search` vs `min_heap` —
  the one contrast where the two names cue *different structural algorithms*.
  For within-family variants (`binary_search` / `find_index` / `smallest_k`),
  qwen is name-invariant. The name token alone does not trigger; the *structural
  prior associated with the name* does.

**Interpretation:** the original taxonomy's `function_name_trigger` class
describes the *effect* correctly at N=15 for `gpt-oss-120b` (pass_rate 0.0), but
the *mechanism* is a sufficient description only for the gpt-oss family. For
qwen, it is a partial one. Different families sit at different points on a
**name-token vs name-structure** axis.

## What this proves

**Claim A (methodology):** the differential name-contrast oracle grounds
`function_name_trigger` at the model level without any `_known_correct_for`
reference. 36 calls, 2 families, 0 hand-authored reference implementations. This
is a *fourth oracle type* alongside the classical reference impl, the Aer
simulator, and the IBM QPU.

**Claim B (finding):** the name-trigger effect refines from "universal" to
"family-and-contrast dependent." This is citable as a refinement of the original
class mechanism.

**What this does NOT do:** it does not eliminate `_known_correct_for` for
`systematic` or `stochastic`. Those classes are spec-divergent — both outcomes
are structurally valid code, and only the *spec text* distinguishes them. No
differential property short of restating the spec can catch that. The differential
oracle is a replacement for `_known_correct_for` **for `function_name_trigger`
only**.

## Honest limitations

**1. N=3 contrasts.** The three contrasts were hand-authored to span the two
structural positions (within-family / cross-algorithm). They are not a random
sample from the space of function names. A wider contrast set could find the
qwen threshold sits elsewhere.

**2. Single run per model, temperature 0.** Name-invariance at qwen could be
stochastic. One re-run with the same contrast would not distinguish "structural
invariance" from "one-shot coincidence." A 3× repeat would.

**3. The differential oracle grounds a weaker claim than `_known_correct_for`.**
`_known_correct_for` proves the model produces the *correct* output.
Differential only proves the model produces *different* output when the name
changes. That is enough for this class (whose whole point is name-triggered
prior activation), not for any class where correctness matters.

**4. Gemini and the Colab tunnel were attempted and dropped.** Gemini 2.0-Flash
and 2.5-Flash both returned 404 (retired); the Colab GGUF tunnel was reached on
`port 8081` with `gpt-oss-20b-Q4_K_M` loaded but the trycloudflare subdomain was
unstable across restarts. Neither reached the differential run. That is recorded
here rather than in the paper because neither produced a result — they are
infrastructure, not findings. If a 3rd family is wanted, use a stable tunnel
(Pinggy or ngrok) or an AI Studio key in `AIza` format.

**5. The API key used for this run was pasted publicly in a session log.** It
was revoked and replaced after the run. The result stands; the artifact records
that the run was executed before rotation.

## Reproduce

```bash
export GROQ_API_KEY="your_groq_key"
python3 80_minimal_differential.py
```

Preflight refuses to run if either model ID is absent. Runtime ~80s (36 calls at
2.2s pace, within Groq's 30 RPM limit).

Files

Path Content
state/minimal_differential.jsonl Per-contrast verdicts and per-input deltas
80_minimal_differential.py The 36-call experiment
71_differential_oracle.py Oracle definition (no execution)
73_run_differential.py Earlier multi-provider version (used before Groq-only simplification)

