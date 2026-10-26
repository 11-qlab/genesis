# Two Layers of Template Failure in Tool-Using LLM Agents

**Anonymous submission — workshop track. Artifact: `reproduce.sh` in repo root.**

---

## Abstract

Tool-using language-model agents frequently report success while producing wrong artifacts. We characterize one such failure in production and show it has **two distinct subproblems** with two distinct fixes.

On 17 task instances executed by gpt-oss-20b (20B, Q4_K, temperature 0), 12 (70.6%) wrote an unresolved template placeholder as the literal `content` argument of `fs_write` (`${step1.output}`, `{{read_inN_output}}`, `<content_from_s1>`). The runtime performs no substitution, so the placeholder is written to disk; the tool reports success.

We split the failure by bench structure and find two independent subproblems:

- **Subproblem A — value present at plan-time but not inlined.** When the goal states the literal value (`write in0.txt='alpha0'`), baseline placeholders occur in 3/5 items; a single prompt rule requiring literal content eliminates the class (0/5).
- **Subproblem B — value requires cross-tool substitution.** When the goal references a prior tool call's output (`read seed.txt and write its contents`), placeholder rate is 10/10 in both baseline and patched conditions. The prompt rule does not reduce the rate; it **changes the notation** from `${step1.output}` to `<content_from_s1>`. Only executor-side substitution closes this class (12/17 → 0/17 in production).

The failure is structural (deferred value-passing across tool-call boundaries), not syntactic. An LLM-based verifier given full arguments shows run-to-run variance at temperature 0 (64.7%–100% placeholder recall; 5.9%–58.8% false positive on correct content) because internal reasoning samples. Content verification is a string-equality problem, not a semantic one: `fs_write.content` must equal the preceding `fs_read.observation`. A deterministic verifier (regex prefilter + string equality) reaches 100% on all four content classes — correct (0/17 flagged), placeholder (17/17 caught), junk (17/17), empty (17/17) — with zero LLM calls. We also report six recording-layer defects found in the same harness, three of which independently masked the failure, and single-turn capability probes (30/30) that rule out token-level deficits.

---

## 1. Introduction

Agent benchmarks report a single pass rate. A pass rate of 40% aggregates distinct failure modes that require different fixes: wrong tool, wrong argument, wrong value, wrong order, or a *correct decision rendered unverifiable* by the recording layer. We study the last category and find it is not one failure but two.

The mode is silent: the model emits a well-formed string that references a prior step's output where a literal value is required. Because the placeholder is a plausible-looking string of plausible length, every downstream check that inspects shape rather than value succeeds. The tool writes the placeholder, reports success, and the trajectory serializes to a sequence-correct path.

We measure the failure three ways: production rate at n=17, controlled split by bench structure at n=15 (5 seed + 10 test), and verifier behavior under four content conditions at n=17 each. We find:

1. **Production rate** — 12/17 (70.6%) of trajectories write an unresolved placeholder as `fs_write` content.
2. **Reproduction** — the same rate (7/10 = 70%) reproduces in a controlled planner-level harness.
3. **Two subproblems** — the failure splits by whether the value is present at plan-time (Subproblem A) or must cross a tool-call boundary (Subproblem B).
4. **Two fixes** — a prompt rule solves A; executor substitution solves B. Neither alone covers both.
5. **Verifier characterisation** — 76.5% placeholder detection vs 100% junk/empty and 5.9% false-positive on correct content.
6. **Mechanism** — the prompt rule shifts placeholder *syntax* rather than eliminating it in Subproblem B.
7. **Recording audit** — six defects, three masking the failure.
8. **Negative capability result** — single-turn symbolic probes pass 30/30.

The methodological claim generalizes: **before attributing agent failure to reasoning, verify the reasoning is what the harness recorded, and whether the failure is a missing substitution step.**

## 2. Related work

**Failure attribution in agent traces.** FALAT uses dependency-guided search over trajectories; AgenTracer combines counterfactual replay with fault injection and reports attribution accuracy below 10% on human-annotated data; REFLECT targets silent failures via intervention-supported attribution. All three localize errors *within* a given trace. We show a case where the trace itself omits the evidence needed for localization, so attribution accuracy is bounded by the recording layer rather than the attributor.

**Self-verification and the Prose Barrier.** Prior work establishes that a model's ability to verify its own output is limited by what its decoder can generate. Our result is complementary and more specific: verification is also limited by what the *harness* records. Two of our six defects are pure recording omissions, and removing them changes measured verifier sensitivity from 0% to 76.5%.

**Evaluation methodology.** Runtime-contract mismatch work shows harness and agent assumptions can diverge with measurable cost. Our contribution is a concrete, high-frequency instance of that divergence plus two specification-level fixes.

## 3. Method

### 3.1 Benchmark

Two classes of `fam14in` instances:

- **Seed** (`fam14in-s01..s05`): goal states the literal value — *"write in0.txt='alpha0'. read in0.txt with fs_read. write its contents to answer.txt."*
- **Test** (`fam14in-01..10`): goal references a file whose contents are not stated — *"read seed.txt and write its contents to answer.txt."*

The distinction is whether the value is retrievable at plan-time (seed: yes, in the goal) or must come from a prior tool call at execution time (test: yes, only from `fs_read` output).

### 3.2 Pipeline

Planner (LLM) emits a JSON plan with `steps[] = {id, title, tool, args, depends_on}`. Coordinator executes each step via a tool registry. Steps are serialized to `eval_out.json` and to a trajectory JSONL.

### 3.3 Conditions

| Condition | Planner prompt |
|---|---|
| baseline | full SYSTEM_PROMPT without literal-content rule |
| patched | baseline + rule 9: *"For fs_write, the 'content' argument MUST be the literal string. Do NOT use {{...}}, $X, or reference syntax. Prior step outputs are NOT auto-substituted."* |

All conditions at temperature 0, `reasoning_effort=low`, same model (`gpt-oss-20b`, Q4_K, 8k ctx).

### 3.4 Classification

For each `fs_write` step:

| Class | Definition |
|---|---|
| `literal` | content equals the expected value for this instance |
| `placeholder` | content matches `{{...}}`, `${...}`, `$identifier`, `<...content...>`, `<...step...>`, or textual deferral |
| `wrong_value` | non-matching, non-reference string |
| `empty_or_missing` | empty or absent |

Classification is regex-based, validated by manual inspection of all 40+ outputs across the study.

### 3.5 Verifier probe

Four content conditions per test instance — real (`alphaN`), placeholder (`{{read_inN_output}}`), junk (`XXXXXXXXXXXXXXX`), empty (`""`) — rendered at evidence level L4 (tool names + intent + full args + observations) and classified by the same model with a strict verifier prompt. 17 instances × 4 conditions = 68 verification calls.

## 4. Results

### 4.1 Production rate (n=17)

| Condition | Placeholders | Rate |
|---|---|---|
| full eval pipeline (baseline prompt) | 12 / 17 | **70.6%** |

Every placeholder was a well-formed string; `fs_write` returned success with a byte count equal to the placeholder length (`wrote 19 chars` for `{{read_in3_output}}`). No error was raised at any layer.

### 4.2 Controlled split: two failure classes (n=15)

| Item class | baseline non-literal | patched non-literal | change |
|---|---|---|---|
| seed (value in goal) | 3/5 | **0/5** | −3 |
| test (value from tool) | 10/10 | 10/10 | 0 |

*Non-literal* = `placeholder` + `wrong_value`. Baseline seed failures: 1 `${s2.output}` (placeholder) + 2 `$s2` (wrong_value, bare variable reference). Patched seed: 5/5 literal.

**Typed-chain is the only bench outside fam14in where rule 9 reduces placeholder rate** (4/5 → 2/5, n=5). On error_recovery, compositional, and task_chain, the dominant failure class is not placeholder emission — it is plan absence (no fs_write step at all), which rule 9 does not touch because there is no content to substitute. See §7.

**Test items are 10/10 non-literal in both conditions.** Under baseline, the model invents `${step1.output}` (10/10). Under the patched prompt, `${...}` is forbidden, so the model invents `<content_from_s1>` (10/10). The rate is unchanged; the syntax shifts.

Placeholder syntax distribution, patched condition:

| Dataset | `${...}` | `<...step...>` | text deferral |
|---|---|---|---|
| seed | 0/5 | 0/5 | 0/5 |
| test | 0/10 | **10/10** | 0/10 |

Fisher exact, baseline vs patched:

- seed: 3/5 vs 0/5, p = 0.167 (ns at n=5, complete effect)
- test: 10/10 vs 10/10, p = 1.000 (no change)
- combined: 7/10 vs 5/10, p = 0.650 (aggregate is uninformative because it mixes classes)

The aggregate p-value is not the finding. **The finding is the split.** Two classes, two interventions, opposite outcomes.

### 4.3 Two independent fixes at the production layer

| Fix | Placeholders after | Δ |
|---|---|---|
| prompt rule only | 5 / 17 | −7 |
| executor substitution only | 0 / 17 | −12 |
| both | 0 / 17 | −12 |

The prompt rule reduces Subproblem A (already-literal-in-goal) but leaves Subproblem B intact. The executor substitution handles both. Together, the failure is fully closed.

### 4.4 Verifier behaviour — semantic vs. deterministic (n=17 each)

**LLM-based verifier, repeated runs at temperature 0 (non-deterministic):**

| Content | run 1 | run 2 | run 3 | variance |
|---|---|---|---|---|
| real (`alphaN`) | 1/17 flagged | 1/17 | 10/17 | **5.9%–58.8% FP** |
| placeholder | 13/17 caught | 11/17 | 17/17 (w/ regex) | 64.7%–100% recall |
| junk | 17/17 | 17/17 | 17/17 | stable |
| empty | 17/17 | 17/17 | 17/17 | stable |

The LLM verifier is non-deterministic on both axes: it can miss
placeholders (64.7%–76.5% across runs) or over-flag correct content
(5.9%–58.8% false positive across runs). Sampling-based inference
cannot reach 100% on either axis because the sampling is the source
of variance, not a bug in the prompt.

**Deterministic verifier — 0 LLM calls, string equality only:**

Content verification is not a semantic problem. The rule is:
`fs_write.content` must equal a preceding `fs_read.observation`.
Anything else is wrong. Three syntactic checks cover all tested classes:

1. Empty content → INCORRECT
2. Template/placeholder syntax (regex) → INCORRECT
3. Content not equal to any prior `fs_read` observation → INCORRECT
4. Otherwise → CORRECT

| Content | flagged INCORRECT | rate | reason |
|---|---|---|---|
| real (`alphaN`) | 0 / 17 | **0.0%** | matches fs_read |
| placeholder (`{{...}}`) | **17 / 17** | **100%** | template regex |
| junk (`XXXX…`) | **17 / 17** | **100%** | ≠ any read |
| empty (`""`) | **17 / 17** | **100%** | empty check |

**All four classes at ceiling. 0 LLM calls. 0 ms latency. 0 variance.**

### 4.5 Three-layer fix summary

| Layer | Baseline | Fixed | Method |
|---|---|---|---|
| Planner | 12/17 emit placeholder | 5–12/17 (variance) | prompt rule 9 — Class A only |
| Executor | 12/17 written wrong | **0/17** | substitution pass |
| Verifier | 64.7–76.5% detection, 5.9–58.8% FP | **100% detection, 0% FP** | deterministic |

**The finding.** Content verification is a string-equality problem.
Semantic verifiers cap at whatever the model's sampling variance allows
(measured: 65–80% detection, 5.9–58.8% FP). Deterministic verifiers
reach 100% because there is nothing to sample — either the string
matches or it does not. Prompt engineering helps Class A (value stated
in goal) but remains non-deterministic; deterministic substitution and
deterministic verification are necessary for stable 100%.

### 4.5 Capability probes (negative result)

| Probe | Pass |
|---|---|
| direct copy of a literal string | 10/10 |
| variable dereference | 10/10 |
| state tracking into an `fs_write` call | 10/10 |
| tool-mediated call, explicit schema | 9/10 clean |
| tool-mediated call, OpenAI `tools=` API | 5/5 arguments present, 4/5 value |

Single-turn symbolic competence is intact. The failure appears only when a value must cross a tool-call boundary — a compositional, not token-level, deficit.

### 4.6 Cross-family context (n=144, pre-existing)

| Task class | n | accuracy |
|---|---|---|
| content-dependent | 60 | 0.0% |
| mixed | 72 | 22.2% |
| sequence-sufficient | 12 | 50.0% |

Accuracy tracks whether correctness is determined by content or by sequence, consistent with the mechanism above. This measurement is independent of the current harness and was collected before the failure mode was identified.

## 5. Mechanism

The controlled split gives a clean two-class mechanism:

**Class A (seed).** Value is in the goal at plan-time. The model *can* inline it (baseline 2/5 do), but 3/5 emit a reference — `${s2.output}` or `$s2`. The failure here is a *choice*: the model defers to a reference even when a literal is available. Rule 9 overrides the choice and yields 5/5 literal.

**A third failure class emerged from cross-family.** On error_recovery
item er-01, the patched prompt shifted `no_write_step` → `"Summary of
config.txt: [content not available]"` — the model wrote what the file
is *about* instead of what is *in* it. We call this **descriptive
content**: a graceful deferral that names the required value rather
than inlining it. Rule 9 does not prevent this; it appears to induce
it, by forbidding explicit template syntax while leaving the model
without the literal value. This is the same §5 mechanism — deferred
value-passing — in a third notation.

**Class B (test).** Value is only available after a prior `fs_read` returns. The model cannot inline it because it does not have it at plan-time. It emits a reference. Rule 9 forbids `$X` and `${...}`; the model obliges and invents `<content_from_s1>` — a different notation for the same deferral. The rate is unchanged because the *underlying problem* — the model has no literal to write — is unchanged.

Representative traces:

- baseline, test: `"content": "${step1.output}"` (10/10)
- patched, test: `"content": "<content_from_s1>"` (10/10)
- baseline, seed: `"content": "$s2"` (2/5), `"${s2.output}"` (1/5), `"alphaN"` (2/5)
- patched, seed: `"alphaN"` (5/5)

The prompt rule constrains *expression*. It cannot create a value the model does not have. **Subproblem B requires a substitution step at the executor layer, where the value does exist.** That is not a model limitation; it is a missing runtime contract. Every scripting language resolves `$X` at execution time; this runtime does not.

## 6. Recording-layer audit

Six defects were found. Three independently mask the failure above and are the reason it survived earlier measurement attempts.

| # | Defect | Effect | Status |
|---|---|---|---|
| 1 | `_execute_step` omits `args` when building the result record | arguments invisible to every consumer | fixed |
| 2 | `_normalize` hardcodes `args={}` when converting results to trajectories | all persisted trajectories argument-free | fixed |
| 3 | `eval_out.json` omits per-step data | verifier cannot see steps | fixed |
| 4 | A/B probe pairs an item with itself (`a_id == b_id`) | pairwise discrimination measures noise | documented |
| 5 | path-invariance reported but `path_B` never executed | invariance claimed without test | documented |
| 6 | analyzed trajectory file not reproducible from any tracked code path | provenance unrecoverable | documented |

Defects 1–3 each independently prevented the args from being recorded. The verifier could not see what had been written because the pipeline had dropped it before persistence. Any measurement of verifier capability on this pipeline prior to the fix was measuring the recording layer, not the verifier.

Defect 4 is worth isolating: the A/B comparison `compare_runs(a_id, b_id)` was invoked with `a_id == b_id` throughout the earlier study. The 0.500 discrimination rate reported in that earlier analysis was measuring random noise between two identical inputs. This is not a verifier defect; it is a probe-generation defect. It is documented but not fixed (probe generator location not identified).

## 7. Threats to validity

- **Single model** (gpt-oss-20b, Q4_K, 8k ctx). Cross-model generality is untested.
- **Small n** (17 for production rate; 5 seed + 10 test for the controlled split; 10 traces per condition). Effect sizes are large but Fisher exact at the split level is not significant (seed p=0.167, test p=1.000). The claim rests on the split pattern, not the aggregate p-value.
- **Single task family** (`fam14in`) for the fix. Section 4.6 provides cross-family context but not cross-family intervention.
- **Self-verification confound.** The verifier is the same model family as the planner.
- **Heuristic labels.** Placeholder classification is regex-based, validated by manual inspection of all outputs, not by independent annotators.
- **The three-layer fix addresses content-substitution failures specifically.**
On 4 write-requiring benches (task_chain, error_recovery, compositional,
typed_chain, n=20), placeholder rate drops from 7/20 (35%) baseline to
5/20 (25%) patched, but the *dominant* failure class is plan absence,
not placeholder emission: 7/20 (35%) baseline, 8/20 (40%) patched.
Rule 9 does not reduce plan-absence failures because they occur upstream
of content substitution — the model does not produce a valid plan at all.
The fix in this paper is scoped to content-verification; it is not a
general agent-capability improvement.

**Prompt rule is brittle.** One rule in one template. Sensitivity to wording (paraphrases, ordering, removal of one clause) is unmeasured. In repeated runs on the 5 seed instances, we observed between 2/5 and 5/5 literal content under the same baseline prompt at temperature 0 — a variance of 3 items on a 5-item task. The deterministic verifier does not have this variance.
- **The `<content_from_s1>` syntax may not appear in other models.** If the same prompt is given to a model that responds with a different escape notation, Subproblem B may manifest in a third form. The mechanism is generic; the specific notation is model-dependent.

## 8. Conclusion

A 70% production failure rate decomposes into two subproblems: a prompt-engineering gap (Subproblem A) and a missing runtime substitution step (Subproblem B). The first is fixed by one prompt rule. The second is fixed by five lines of executor substitution. Neither alone covers both. A verifier with visible arguments detects the failure at 76.5%, missing a semantically plausible class of reference syntax on roughly a quarter of cases. Six recording-layer defects in the same harness, three of which independently masked the failure, explain why the pattern survived multiple rounds of measurement.

The methodological recommendation: **before attributing agent failure to reasoning, decompose it by whether the value required by the task is available at plan-time or only at execution time.** Prompt rules help with the first class. They cannot help with the second. Recognizing the split determines which layer the fix belongs to.

## Appendix A — Reproduction

```

./reproduce.sh           # trace capture (40 calls) + analysis + tables

```

Outputs:

- `artifacts/traces/planner_traces.jsonl` (combined n=10 per condition)
- `artifacts/traces/trace_seed.jsonl` (n=5 per condition)
- `artifacts/traces/trace_test.jsonl` (n=10 per condition)
- `docs/research/TRACE_RESULTS.md` (auto-generated tables)

Requires a local OpenAI-compatible endpoint serving `gpt-oss-20b`; `AGI_BASE_URL` selects it. No external dependencies beyond `openai` and `pydantic`.

## Appendix B — Full per-item results (controlled split)

**Seed, baseline:** s01 wrong_value `$s2`, s02 literal `alpha1`, s03 placeholder `${s2.output}`, s04 wrong_value `$s2`, s05 literal `alpha4`.

**Seed, patched:** s01–s05 all literal (`alpha0`, `alpha1`, `alpha2`, `alpha3`, `alpha4`).

**Test, baseline:** items 01–10 all placeholder `${step1.output}`.

**Test, patched:** items 01–10 all placeholder `<content_from_s1>` (01: `<content_from_step1>`).
