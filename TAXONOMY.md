# Failure Taxonomy

Version 1.4 — generated 2026-10-27T19:39:18.527124Z

## Summary

Three failure classes, all attributable to spec text activating a divergent canonical prior.

| Class | Subtype | Task | Original | Recovery |
|---|---|---|---|---|
| prior_override_failure | systematic | merge_intervals | 0.00 | rule-only: 1.00 |
| prior_override_failure | stochastic | approximately_equal | 0.653 | rule-only: 1.00 |
| under_specification_failure | spec_ambiguity | binary_search_leftmost | 0.00 | rule-only: 1.00 |

## Recipe validation (held-out tasks)

| Task | Subtype | Ambiguous | Recipe | Δ | Verdict |
|---|---|---|---|---|---|
| valid_palindrome | under_specification | 0.0 | 1.0 | +1.0 | confirms_prior_override |
| majority_element | prior_override_systematic | 0.0 | 1.0 | +1.0 | confirms_prior_override |
| isomorphic_strings | prior_override_systematic | 1.0 | 1.0 | +0.0 | not_a_valid_divergence_test |

Recipe is validated with a specificity constraint: prior_override_failure is only diagnostic when the canonical form is genuinely common AND genuinely contradicts the spec. Two of three held-out tasks confirmed the recipe; the third revealed the constraint that the recipe requires empirical prior verification, not static analysis.

## Specificity constraint (from validation)

**Prior_override_failure is diagnostic only when**:

1. The canonical code form is common in the model's training distribution, AND
2. The canonical form genuinely contradicts the spec.

`isomorphic_strings` failed criterion 1 — the model's prior for bijection is already strong, so the task doesn't activate the naive implementation. **Recipe step 1 must be empirical** (a small pre-flight batch of trials) not static analysis of LeetCode solutions.

## Control
qwen/qwen3.8-27b — 9/9 on both tasks, both specs

## Conclusion
Benchmark spec text is not neutral. Every hedge word ('touching', 'the index', 'handle zero') activates a canonical prior that may contradict the test. Spec precision — even without test disclosure — recovers the failure by activating the correct prior.

**Specificity caveat:** the failure only occurs when the canonical prior is strong enough to override the spec, and weak enough that the spec's correct reading doesn't dominate by default. Verifying both conditions empirically is step 1 of the recipe.

## Inverse-scaling finding
On spec-divergent tasks, the model with the strongest coding priors (`gpt-oss-120b`) fails at a higher rate than the weaker models, because the weaker models lack the offending prior.

Evidence: approximately_equal / original — pooled: 120b 32/49 (~65%); qwen 18/18 (100%); 20b 18/18 (100%).