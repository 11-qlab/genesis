# PTE — Finding Summary (2026-10-27)

## One-sentence result

The cross-tool binding failure in LLM planners is a **schema-adequacy problem**,
not a model limitation. Adding one typed deferral slot to the plan schema closes
the failure class at 100% across 4 models, 3 architectures, 2 providers.

## The claim, three parts

1. **Diagnosis** — the plan schema has `content: str` with no representation
   for "this value comes from step N." The model invents dialects
   (`${}`, `{{}}`, `$sN`, prose, `{'$ref':...}`). None resolve.
   Evidence: H009, `artifacts/esf/typed_holes_probe.json`.

2. **Fix** — one typed slot: `content: str | {__deferred__: {from, field}}`.
   Executes 12/12 strict, 0 unresolved, no fuzzy fallback.
   Evidence: H010, `artifacts/esf/h009_execution.json`.

3. **Deployability** — production rule 9 does not interfere (H011). Survives
   all soft prompt pressure; only a specific substitutive rule flips it.
   Evidence: `artifacts/esf/typed_holes_rule9.json`, `adversarial_matrix.json`.

## Scope (measured, not assumed)

| Model | Provider | Arch | Scale | typed_holes exec |
|---|---|---|---|---|
| gpt-oss-20b | ollama + Groq | GPT-OSS | 20B | **12/12 strict** |
| gpt-oss-120b | Groq | GPT-OSS | 120B | **12/12** |
| qwen3.8-27b | Groq | Qwen | 27B | **12/12** |
| allam-2-7b | Groq | Allam | 7B | **0/12 without example; 12/12 strict with one-shot example** |

**Boundary:** 7B needs one example in the prompt. Above ~20B, schema alone
suffices. Source: `artifacts/esf/cross_groq_typed.json`,
`artifacts/esf/allam_example_test.json` (no result files yet — H012/H013 pending).

## Extensions found

- **Multi-hop** — 5-step chain with 2 chained deferrals, 3/3 valid
  (`scripts/_experiments/chain_test.py`).
- **Transform** — single-op transforms close with `transform: <op>` slot +
  bounded vocabulary (7/8). Composition (t7, two ops) fails — **next boundary**
  (`artifacts/esf/transform_test.json`).
- **Harm** — "do NOT use deferred, use 'PLACEHOLDER'" produces 0/4 correct
  files. Prohibition without viable substitute actively causes failure.

## What is NOT done

- `results/H012.json` (cross-model) — raw in `artifacts/esf/cross_groq_typed.json`
- `results/H013.json` (transform) — raw in `artifacts/esf/transform_test.json`
- Transform composition: `transform: [op1, op2]` untested
- Bench generalization beyond `fam14in` (n=12)
- Compare against ReWOO's `#E1` placeholder approach (prior art, not yet cited)

## How to resume

1. Read this file.
2. `git log --oneline -20` for the session's commit trail.
3. Open `artifacts/esf/*.json` for raw data behind each claim.
4. If continuing: write H012/H013 result files first (10 min, no calls),
   then transform composition (8 calls).
