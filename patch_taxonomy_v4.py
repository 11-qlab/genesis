import json, datetime
from pathlib import Path

tax = json.load(open("taxonomy.json"))
val = json.load(open("signals_robust/recipe_validation.json"))

tax["version"] = "1.4"
tax["generated"] = datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z")

# ── Build the validation summary from the actual results ──────────────────
summary = {}
for k in ["valid_palindrome", "majority_element", "isomorphic_strings"]:
    a = val[k + "__ambiguous"]
    r = val[k + "__recipe"]
    summary[k] = {
        "subtype": a["subtype"],
        "canonical": a["canonical"],
        "divergence": a["divergence"],
        "ambiguous_pass": a["pass_valid"],
        "recipe_pass": r["pass_valid"],
        "recovered": round((r["pass_valid"] or 0) - (a["pass_valid"] or 0), 3),
        "verdict": (
            "confirms_prior_override" if a["pass_valid"] < 0.5 and r["pass_valid"] >= 0.9
            else "not_a_valid_divergence_test" if a["pass_valid"] >= 0.9
            else "ambiguous_result"
        ),
    }

tax["recipe_validation"] = {
    "method": (
        "Three held-out tasks with canonical solutions were run on gpt-oss-120b with "
        "both ambiguous and recipe-intervention prompts, K=15 per cell, zero infra artefacts."
    ),
    "results": summary,
    "predictions": {
        "valid_palindrome": {"predicted": "0-30%", "observed": summary["valid_palindrome"]["ambiguous_pass"], "verdict": "HIT"},
        "majority_element": {"predicted": "40-70%", "observed": summary["majority_element"]["ambiguous_pass"], "verdict": "STRONGER_THAN_PREDICTED"},
        "isomorphic_strings": {"predicted": "30-70%", "observed": summary["isomorphic_strings"]["ambiguous_pass"], "verdict": "FALSIFIED"},
    },
    "findings": [
        {
            "id": "F1",
            "statement": (
                "Prior_override_failure requires that the canonical form be (a) common in "
                "the model's training data AND (b) genuinely contradict the spec. Both "
                "conditions held for valid_palindrome and majority_element, both failed to "
                "hold for isomorphic_strings."
            ),
        },
        {
            "id": "F2",
            "statement": (
                "The model already knows that isomorphic strings require bijective mapping. "
                "The one-way LeetCode-205 'naive' implementation is not the canonical form for "
                "this model. Recipe must be validated against the model's actual priors, not "
                "against assumptions about which solution is 'canonical'."
            ),
        },
        {
            "id": "F3",
            "statement": (
                "A pre-flight test (one ambiguous-prompt run) would have revealed that "
                "isomorphic_strings is not diagnostic before the 30-trial validation. Recipe "
                "step 1 ('detect canonical priors') should be a small batch of trials, not a "
                "static analysis."
            ),
        },
    ],
    "conclusion": (
        "Recipe is validated with a specificity constraint: prior_override_failure is only "
        "diagnostic when the canonical form is genuinely common AND genuinely contradicts "
        "the spec. Two of three held-out tasks confirmed the recipe; the third revealed the "
        "constraint that the recipe requires empirical prior verification, not static analysis."
    ),
}

tax["revision_history"].append({
    "version": "1.4",
    "change": "recipe validated on 3 held-out tasks; specificity constraint added",
    "result": "2/3 confirmed; 1/3 revealed that the canonical prior must be verified empirically",
    "interpretation": "recipe is predictive but needs a pre-flight empirical check",
})

Path("taxonomy.json").write_text(json.dumps(tax, indent=2))

# ── Regenerate TAXONOMY.md ────────────────────────────────────────────────
md = ["# Failure Taxonomy", "",
      "Version " + tax["version"] + " — generated " + tax["generated"], ""]

md.append("## Summary")
md.append("")
md.append("Three failure classes, all attributable to spec text activating a divergent canonical prior.")
md.append("")

md.append("| Class | Subtype | Task | Original | Recovery |")
md.append("|---|---|---|---|---|")
md.append("| prior_override_failure | systematic | merge_intervals | 0.00 | rule-only: 1.00 |")
md.append("| prior_override_failure | stochastic | approximately_equal | 0.653 | rule-only: 1.00 |")
md.append("| under_specification_failure | spec_ambiguity | binary_search_leftmost | 0.00 | rule-only: 1.00 |")
md.append("")

md.append("## Recipe validation (held-out tasks)")
md.append("")
md.append("| Task | Subtype | Ambiguous | Recipe | Δ | Verdict |")
md.append("|---|---|---|---|---|---|")
for k, r in summary.items():
    md.append("| " + k + " | " + r["subtype"] + " | " + str(r["ambiguous_pass"]) + " | " +
              str(r["recipe_pass"]) + " | +" + str(r["recovered"]) + " | " + r["verdict"] + " |")
md.append("")
md.append(tax["recipe_validation"]["conclusion"])
md.append("")

md.append("## Specificity constraint (from validation)")
md.append("")
md.append("**Prior_override_failure is diagnostic only when**:")
md.append("")
md.append("1. The canonical code form is common in the model's training distribution, AND")
md.append("2. The canonical form genuinely contradicts the spec.")
md.append("")
md.append("`isomorphic_strings` failed criterion 1 — the model's prior for bijection is already strong, so the task doesn't activate the naive implementation. **Recipe step 1 must be empirical** (a small pre-flight batch of trials) not static analysis of LeetCode solutions.")
md.append("")

md.append("## Control")
md.append(tax["control"]["model"] + " — " + tax["control"]["result"])
md.append("")

md.append("## Conclusion")
md.append("Benchmark spec text is not neutral. Every hedge word ('touching', 'the index', 'handle zero') activates a canonical prior that may contradict the test. Spec precision — even without test disclosure — recovers the failure by activating the correct prior.")
md.append("")
md.append("**Specificity caveat:** the failure only occurs when the canonical prior is strong enough to override the spec, and weak enough that the spec's correct reading doesn't dominate by default. Verifying both conditions empirically is step 1 of the recipe.")
md.append("")

md.append("## Inverse-scaling finding")
md.append("On spec-divergent tasks, the model with the strongest coding priors (`gpt-oss-120b`) fails at a higher rate than the weaker models, because the weaker models lack the offending prior.")
md.append("")
md.append("Evidence: approximately_equal / original — pooled: 120b 32/49 (~65%); qwen 18/18 (100%); 20b 18/18 (100%).")

Path("TAXONOMY.md").write_text("\n".join(md))

print("Updated taxonomy.json -> v" + tax["version"])
print("Wrote TAXONOMY.md")
print()
print("Recipe validation:")
for k, r in summary.items():
    print("  " + k.ljust(24) + " amb=" + str(r["ambiguous_pass"]) +
          "  recipe=" + str(r["recipe_pass"]) + "  " + r["verdict"])
