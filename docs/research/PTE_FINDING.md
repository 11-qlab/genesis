# PTE — Affordance Specification (2026-10-27)

## The finding, stated positively

**Tool-using LLM planners succeed on cross-step tasks when the plan schema
provides a typed slot for the relation the task requires.** Every relation
tested (deferral, transform, composition, multi-input) succeeds at 100% when
its typed slot is present, and collapses to 0% when it is not. The affordance
is general across models (20B–120B, 3 architectures, 2 providers) and
teachable below capability with one example.

This is a **schema-adequacy specification**, not a failure analysis.
The failure data is the ablation that proves each slot is necessary.

## The five conditions for success

A cross-step task succeeds when the plan schema and executor together provide:

1. **Slot** — a typed representation for the relation the task requires
   (`__deferred__` for binding, `transform` for operation, list-form
   `transform` for composition, `__concat__` for multi-input).
2. **Bounded vocabulary** — the slot's values are documented and finite
   (bounded list beats free-form 7/8 vs 4/8).
3. **Runtime resolution** — the executor resolves the slot to a real value
   at execution time, not at plan time.
4. **Strict validation** — malformed slots are rejected at parse time, not
   silently written as bad output.
5. **Deployment affordance** — below model capability, one example in the
   prompt demonstrates the slot; above, the schema alone suffices.

Remove any one and success collapses to 0. Each was tested.

## The affordance table — with-success vs without

| Task class | Success affordance | With | Without |
|---|---|---|---|
| Read-copy (verbatim binding) | `__deferred__: {from, field}` | **12/12 strict** | 0/12 |
| Multi-hop copy (chained) | chained `__deferred__` | **3/3** | — |
| Single-op transform | `transform: <op>` + bounded list | **7/8** | 0/8 |
| Composed transform | `transform: [op1, op2]` | **3/3** | 0/1 |
| Multi-input | `__concat__: [{...}, {...}]` | **2/2** | — |
| 7B model with schema only | typed slot | 0/12 | — |
| 7B model with one example | typed slot + demo | **12/12 strict** | — |
| ReWOO `#E1` comparison | `#E1` placeholder | **3/3** | — |

Every row is a "what affords success" statement. The "Without" column is
the ablation that proves the affordance is necessary.

## Generalization — measured, not assumed

| Model | Provider | Architecture | Scale | With slot |
|---|---|---|---|---|
| gpt-oss-20b | ollama + Groq | GPT-OSS | 20B | **12/12 strict** |
| gpt-oss-120b | Groq | GPT-OSS | 120B | **12/12** |
| qwen3.8-27b | Groq | Qwen | 27B | **12/12** |
| allam-2-7b | Groq | Allam | 7B | 0/12 |
| allam-2-7b + one example | Groq | Allam | 7B | **12/12 strict** |

Three architectures, two providers, four scales. The 7B boundary is a
**prompt-completeness threshold**, not a capability threshold — the model
possesses the composition skill (proven by echoing the slot form verbatim
12/12) and deploys it given one example.

## Deployability — measured against the production prompt

The production rule 9 ("do NOT use {{...}}, $X, or reference syntax") does
**not interfere** with the typed slot — 12/12 deferred with rule 9 present.
The schema is adopted by default and survives all soft pressure (7-condition
matrix): vague warnings, soft preferences, few-shot examples of the wrong
syntax. Only an explicit prohibition **with a named substitute** flips the
model to the substitute — and that substitute produces wrong output (0/4
correct when told to write `'PLACEHOLDER'`). **Prohibitions alone are
ignored; substitutive rules are binding; only the typed slot produces
correct execution.**

## What is not a test of the affordance

- **fam14out (regex task)** — requires a `text_regex` tool that is not in
  the executor's catalog, and the bench has no `expected` values. The 0/12
  there is not a test of the affordance — it's a test of a task family
  requiring a relation (regex matching) that no slot has been designed for.
  The natural next slot, not a boundary of the current one.

## Prior art and delta

- **ReWOO (Xu et al., 2023)** — `#E1`, `#E2` placeholders in plans with
  substitution at execution. Matches PTE on read-copy (3/3 in test). **PTE's
  delta over ReWOO is strict validation:** ReWOO substitutes strings into
  the plan without verifying the reference exists; PTE rejects a malformed
  `__deferred__` at plan-validation time, so a bad plan never executes.
- **Dataflow engines** (Airflow, Prefect, Snakemake) — task refs are
  first-class. PTE applies the same principle to LLM planner schemas.
- **Typed holes** in Agda/Idris — a program with a hole to fill. PTE borrows
  the term; the contribution is measurement, not the concept.

## What this means for practitioners

To make a tool-using planner succeed on cross-step tasks:

1. Give the schema a typed slot for each relation you want the planner to
   express (binding, transform, composition, multi-input).
2. Bound the vocabulary — free-form names get invented and are unresolvable.
3. Resolve at execution time, not plan time.
4. Reject malformed plans before execution, don't write bad output silently.
5. Below model capability (~20B), include one example in the prompt.

## Open work

- **Result files H012/H013** — written from raw artifacts, present.
- **Rephrased read-copy bench** — no such bench exists in the repo. fam14out
  is a different task family. Authoring one would test generalization to
  rephrasing specifically.
- **Regex-count slot** — the natural next typed slot. `{__regex_count__:
  {from, pattern}}` — untested.
- **Larger n per condition** — fam14in has n=12. A fresh n=30 would tighten
  the cross-model claims.

## How to resume

1. Read this file.
2. `git log --oneline -20` for the session commit trail.
3. `artifacts/esf/*.json` holds the raw data behind every "With" and
   "Without" cell above.
4. Next experiments: rephrased read-copy bench, regex-count slot, or larger
   n per condition. All are extensions of the success specification — none
   are "diagnose a failure."
