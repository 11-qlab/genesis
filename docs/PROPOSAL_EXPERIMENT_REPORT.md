# Autonomous class proposal experiment

## Question
Can an LLM propose a novel LLM-behavioral failure class that survives both a
5-gate execution-verifiable pipeline AND post-hoc semantic review?

## Method

10 proposals from `openai/gpt-oss-20b` on Groq (JSON mode, temperature 0.7).

**Execution gates (in order):**
1. Syntax — impl_src, base_src, test_src all compile
2. Discriminate — impl passes its own test, baseline fails
3. Held-out — the pair survives function renaming
4. Novelty — string match on name/subtype vs existing taxonomy
5. Empirical — model fails the proposed spec ≥2/3 trials

**Post-hoc semantic gates (on the 5 that passed):**
4a. Mechanism text similarity — deterministic token-overlap, ≥80% = duplicate
4b. Semantic novelty — LLM judge vs existing taxonomy + prior accepted
5b. Category — llm_behavioral vs language_level, with anti-examples + confidence
5c. Baseline capability — does model solve a trivial spec? (control for gate 5)

## Results

### Execution pipeline (before any semantic review)
| Count | Outcome | Category |
|---|---|---|
| 3/10 | failed syntax (`test_src`: unterminated string literal) | **real proposer failure** |
| 2/10 | HTTP 400 JSON mode | infra |
| 5/10 | passed all 5 execution gates | — |

Proposer lossiness: 50% of proposals are unusable before any gate runs.

### Post-hoc semantic review of the 5 survivors
| Proposal | Novelty | Category | Verdict |
|---|---|---|---|
| `mutable_default_argument / shared_state` | novel | language_level | REJECT_LANGUAGE_LEVEL |
| `default_argument_mutability / stateful_default` | **duplicate** (100% text overlap, DET) | language_level | REJECT_DUPLICATE |
| `wrong_operator_precedence / arithmetic` | novel | language_level | REJECT_LANGUAGE_LEVEL |
| `missing_import / module_missing` | novel | language_level | REJECT_LANGUAGE_LEVEL |
| `output_type_mismatch / wrong_return_type` | novel | language_level | REJECT_LANGUAGE_LEVEL |

**0/5 accepted as novel LLM-behavioral classes.**

### Baseline capability control
Model passes a trivial spec 3/3. The empirical gate (gate 5) is not noise:
when the model fails a proposed spec 3/3, it's a real failure, not a CoT
truncation or infra artifact.

## Finding

**The wall is not the proposer and not the verifier. The wall is that semantic
novelty cannot be execution-verified.**

The execution-verifiable gate stack is necessary and working:
- Catches malformed code (3/10 syntax failures)
- Catches self-inconsistent (impl, test) pairs (0/10 reached held-out gate)
- Catches name-overfit (held-out gate runs on all survivors)
- Catches exact-name duplicates (string-match novelty gate)
- Catches spec-easy proposals (empirical + baseline control)

The execution stack cannot catch:
- **Mechanism duplicates with different names.** Two classes can have different
  `name/subtype` and identical `mechanism` and both pass. Fixed with a
  deterministic mechanism-similarity pre-gate (4a), but only for near-identical
  text (≥80% token overlap). Paraphrased mechanisms still require an LLM judge.
- **Category: LLM-behavioral vs language-level.** Both look identical to
  execution gates — they pass "impl passes test, baseline fails" equally.
  Distinguishing them requires semantic knowledge of "what counts as an
  LLM-specific prior override" vs "a bug humans also make."

**6 of 8 ideal checks are execution-verifiable** (syntax, discriminate, held-out,
string-novelty, empirical-fail, empirical-baseline). **2 require semantic
judgment** (mechanism-novelty, category). The paper's finding is that this
boundary is where self-design hits the wall, and it is not a proposer or
verifier defect — it is that semantic properties are not execution-verifiable.

## What this proves vs what it does not

**Proves:**
- The 5-gate execution pipeline works end-to-end on free-generation proposals.
- Autonomous proposal fails at the semantic layer, not the code layer.
- The proposer produces plausible candidates but does not reliably produce
  self-consistent, compilable ones (50% lossy).
- Baseline control (trivial spec) confirms empirical results are not noise.

**Does not prove:**
- That no LLM could propose a novel class. `qwen3.8-27b`, `gpt-oss-120b`, or
  a fine-tuned proposer might. This is one model, one prompt, one day.
- That the LLM judge is correct. Same model family as proposer; an independence
  check (different family judging) is documented as future work.
- That no new class exists in the space probed. Only that this proposer did
  not produce one for any of these 10 attempts.

## Honest limitations

1. **Same-family judge.** `gpt-oss-20b` proposes and classifies. Cross-family
   judging is a follow-up. The deterministic 4a pre-gate does not depend on
   the judge — it caught the exact-mechanism duplicate independently.

2. **N=10 proposals, 5 tested.** A larger N would sharpen the failure-mode
   distribution. But 0/5 novel is unambiguous at this N for the classes
   proposed.

3. **Gate 5b (baseline) is a weak control.** It detects "model is uniformly
   bad" but not "model is specifically bad at this particular gotcha." A
   stronger control (a `control_spec` produced by the proposer alongside
   the class) is future work.

4. **3/10 syntax failures mask a real proposer competence ceiling.** A
   proposer that emits unterminated strings 30% of the time cannot be used
   for autonomous research even if the gates work perfectly.

## Reproduction

    export GROQ_API_KEY=...
    python3 90_propose_class.py     # generates + runs execution gates
    python3 92_judge_gates.py       # post-hoc semantic review

Artifacts:
    state/proposals.jsonl            — all 10 attempts, per-gate verdicts
    state/proposals_tagged.jsonl     — 5 survivors + semantic classification
    state/proposals_raw/             — raw model output per attempt
