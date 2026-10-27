import json, datetime
from pathlib import Path

tax = json.load(open("taxonomy.json"))
loose = json.load(open("signals_robust/loose_ends.json"))

tax["version"] = "1.3"
tax["generated"] = datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z")

def pv(key):
    v = loose.get(key, {}).get("pass_valid")
    return v

# ── Update stochastic subtype with rule_only + threshold ───────────────────
for cls in tax["classes"]:
    if cls["subtype"] != "stochastic":
        continue
    ev = cls["evidence"]
    ev["rule_only_intervention"] = {
        "prompt": loose["approximately_equal__rule_only"]["details"][0].get("prompt", ""),
        "n": loose["approximately_equal__rule_only"]["valid"],
        "n_passed": loose["approximately_equal__rule_only"]["passed"],
        "pass_valid": loose["approximately_equal__rule_only"]["pass_valid"],
        "rule_text": "absolute tolerance is a small nonzero value (not 0.0)",
        "source": "close_loose_ends.py",
    }
    ev["threshold_intervention"] = {
        "n": loose["approximately_equal__threshold"]["valid"],
        "n_passed": loose["approximately_equal__threshold"]["passed"],
        "pass_valid": loose["approximately_equal__threshold"]["pass_valid"],
        "rule_text": "absolute tolerance of at least 1e-12",
        "source": "close_loose_ends.py",
    }

    rule_only_ok  = ev["rule_only_intervention"]["pass_valid"]  >= 0.9
    threshold_ok  = ev["threshold_intervention"]["pass_valid"]  >= 0.9

    if rule_only_ok:
        cls["remediation"] = (
            "State the divergent rule explicitly (nonzero absolute tolerance). "
            "Rule statement alone is sufficient; the specific numeric value is not required."
        )
    elif threshold_ok:
        cls["remediation"] = (
            "State the specific threshold (abs_tol >= 1e-12). Rule-only is insufficient; "
            "the numeric value must be explicit."
        )
    else:
        cls["remediation"] = (
            "Even threshold-explicit prompt does not recover the cell; the failure "
            "is deeper than specification."
        )

# ── Add the new under_specification_failure class ──────────────────────────
bs_orig = loose["binary_search_leftmost__original"]
bs_rule = loose["binary_search_leftmost__rule_only"]

tax["classes"].append({
    "name": "under_specification_failure",
    "subtype": "spec_ambiguity",
    "signature": (
        str(bs_orig["pass_valid"]) + " pass on ambiguous spec ('the index'); "
        + str(bs_rule["pass_valid"]) + " pass on rule-stated spec ('the LEFTMOST index')"
    ),
    "mechanism": (
        "Spec uses a phrase ('the index') that has multiple valid interpretations. The "
        "canonical LeetCode-style solution to the general class (binary_search) returns "
        "any matching index, which satisfies one reading but not the one the test requires. "
        "The model is not violating a stated rule; it is filling an ambiguous spec with the "
        "canonical interpretation. When the ambiguity is resolved ('the LEFTMOST index'), "
        "the model writes the correct form."
    ),
    "evidence": {
        "task": "binary_search_leftmost",
        "original_spec": "Write a Python function binary_search(arr, x) that returns the index of x in sorted arr, or -1 if absent.",
        "rule_only_spec": "Write a Python function binary_search(arr, x) that returns the LEFTMOST index of x in sorted arr (the smallest index if x appears more than once), or -1 if absent.",
        "affected_models": {
            "openai/gpt-oss-120b": {
                "n": bs_orig["valid"], "n_passed": bs_orig["passed"],
                "pass_valid": bs_orig["pass_valid"],
            },
        },
        "rule_only_intervention": {
            "n": bs_rule["valid"], "n_passed": bs_rule["passed"],
            "pass_valid": bs_rule["pass_valid"],
        },
    },
    "remediation": (
        "Resolve the ambiguity in the spec. When the divergent reading is stated "
        "explicitly ('the LEFTMOST index'), the model writes the correct form."
    ) if bs_rule["pass_valid"] >= 0.9 else (
        "Rule-stated spec does not recover the cell; the failure is capability-level, not spec-level."
    ),
    "relationship_to_prior_override": (
        "Prior_override_failure: spec states the rule, model produces a code form "
        "that contradicts it. Under_specification_failure: spec admits two readings, "
        "model produces the canonical one, test requires the other. Both fixed by "
        "spec precision, but through different mechanisms."
    ),
})

# ── Unified conclusion across all three classes ────────────────────────────
ae_orig = 32/49
ae_rule = loose["approximately_equal__rule_only"]["pass_valid"]
ae_thr  = loose["approximately_equal__threshold"]["pass_valid"]

all_recovered = (
    loose["approximately_equal__rule_only"]["pass_valid"]  >= 0.9 or
    loose["approximately_equal__threshold"]["pass_valid"]  >= 0.9
) and bs_rule["pass_valid"] >= 0.9

tax["conclusion"] = {
    "statement": (
        "All three failure classes (systematic prior_override, stochastic prior_override, "
        "and under_specification) are attributable to spec text activating a canonical "
        "solution that diverges from the test. Every class recovers to near-ceiling when "
        "the divergent requirement is stated explicitly in the spec."
    ) if all_recovered else (
        "The three failure classes are recoverable by spec precision in the cases tested, "
        "with the caveat that at least one cell does not fully recover, indicating a "
        "capability component alongside the specification component."
    ),
    "ladder": {
        "approximately_equal": {
            "original": round(ae_orig, 3),
            "rule_only_nonzero": ae_rule,
            "threshold_1e12": ae_thr,
        },
        "binary_search_leftmost": {
            "original": bs_orig["pass_valid"],
            "rule_only_leftmost": bs_rule["pass_valid"],
        },
    },
    "practical_implication": (
        "Benchmark spec text is not neutral. Every hedge word ('touching', 'the index', "
        "'handle zero') activates a canonical prior that may contradict the test. "
        "Spec precision — even without test disclosure — recovers the failure by "
        "activating the correct prior. This suggests spec-writing standards for agent "
        "benchmarks: state divergent rules explicitly, avoid hedged adjectives when the "
        "test requires a specific interpretation."
    ),
}

Path("taxonomy.json").write_text(json.dumps(tax, indent=2))

# ── Regenerate TAXONOMY.md ────────────────────────────────────────────────
md = ["# Failure Taxonomy", "", "Version " + tax["version"] + " — generated " + tax["generated"], ""]
md.append("## Summary")
md.append("")
md.append("Three failure classes, all attributable to spec text activating a divergent canonical prior:")
md.append("")
md.append("| Class | Subtype | Task | Original | Recovery |")
md.append("|---|---|---|---|---|")

# Prior override systematic
md.append("| prior_override_failure | systematic | merge_intervals | 0.00 (N=9) | rule-only: 1.00 (N=20) |")
# Prior override stochastic
ae_row_orig = "| prior_override_failure | stochastic | approximately_equal | " + str(round(ae_orig,3)) + " (N=49) | "
ae_row_orig += "rule-only: " + str(ae_rule) + " · threshold: " + str(ae_thr) + " |"
md.append(ae_row_orig)
# Under spec
md.append("| under_specification_failure | spec_ambiguity | binary_search_leftmost | " +
          str(bs_orig["pass_valid"]) + " (N=" + str(bs_orig["valid"]) + ") | rule-only: " +
          str(bs_rule["pass_valid"]) + " (N=" + str(bs_rule["valid"]) + ") |")
md.append("")

md.append("## Control")
md.append(tax["control"]["model"] + " — " + tax["control"]["result"])
md.append("")

md.append("## Conclusion")
md.append(tax["conclusion"]["statement"])
md.append("")
md.append("**Practical implication:** " + tax["conclusion"]["practical_implication"])
md.append("")

md.append("## Inverse-scaling finding")
md.append(tax["finding_inverse_scaling"]["statement"])
md.append("")
md.append("Evidence: " + tax["finding_inverse_scaling"]["evidence"])

Path("TAXONOMY.md").write_text("\n".join(md))
print("Updated taxonomy.json -> v" + tax["version"])
print("Wrote TAXONOMY.md")
print()
print("approx_equal ladder:  original=" + str(round(ae_orig,3)) + "  rule=" + str(ae_rule) + "  threshold=" + str(ae_thr))
print("binary_search ladder: original=" + str(bs_orig["pass_valid"]) + "  rule=" + str(bs_rule["pass_valid"]))
