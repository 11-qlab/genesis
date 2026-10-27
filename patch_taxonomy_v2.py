import json, datetime
from pathlib import Path

tax = json.load(open("taxonomy.json"))
tax["version"] = "1.2"
tax["generated"] = datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z")

for cls in tax["classes"]:
    if cls["subtype"] != "systematic":
        continue
    ev = cls["evidence"]

    # Rule-only intervention
    ev["rule_only_intervention"] = {
        "prompt": (
            "merge overlapping closed intervals AND intervals whose endpoints "
            "touch (the end of one equals the start of the next)"
        ),
        "model": "openai/gpt-oss-120b",
        "n": 20, "n_passed": 20, "pass_valid": 1.0,
        "ci95": [0.84, 1.00],
        "source": "tighten_without_example.py",
        "note": "Rule stated without an example — example was not necessary.",
    }

    cls["remediation"] = (
        "State the divergent rule explicitly in the spec (e.g. 'the end of one equals "
        "the start of the next'). An example is not necessary. The failure is a "
        "spec-activation failure, not a test-matching failure."
    )
    cls["mechanism"] = (
        "The natural-language spec activates the canonical LeetCode-56 solution to "
        "merge_intervals, whose strict '<' does not merge touching intervals. When "
        "the spec states the touching rule explicitly, the model activates a "
        "different prior and writes '<=' on 20/20 trials. The mechanism is "
        "spec-driven prior selection, not code-level inability."
    )

tax["conclusion"] = {
    "statement": (
        "Both prior_override_failure subtypes are eliminated by spec precision alone. "
        "For the systematic subtype, stating the rule without an example yields 20/20. "
        "For the stochastic subtype, naming the abs_tol default yields 9/9. "
        "In neither case is a test case or example required — the mechanism is "
        "which canonical prior the English activates."
    ),
    "practical_implication": (
        "Benchmark specs should state divergent requirements as explicit rules, not "
        "as hedged adjectives ('touching') that the canonical solution can override."
    ),
}

tax["revision_history"] = tax.get("revision_history", []) + [
    {
        "version": "1.2",
        "change": "rule_only_intervention added for systematic subtype",
        "result": "20/20 = 1.00 with rule-only prompt — example is not necessary",
        "interpretation": "remediation is spec precision, not test disclosure",
    }
]

Path("taxonomy.json").write_text(json.dumps(tax, indent=2))

# Regenerate TAXONOMY.md
md = ["# Failure Taxonomy", "", "Version " + tax["version"] + " — generated " + tax["generated"], ""]

md.append("## Classes")
md.append("")
md.append("| Class | Subtype | Task | Original | Rule-stated | Rule+example |")
md.append("|---|---|---|---|---|---|")
for c in tax["classes"]:
    t = c["evidence"]["task"]
    for m, ev in c["evidence"]["affected_models"].items():
        pv = str(ev.get("pass_valid", "n/a"))
        tight = str(c["evidence"]["tightened"]["pass_valid"])
        rule_only = c["evidence"].get("rule_only_intervention", {}).get("pass_valid")
        rule_str = str(rule_only) if rule_only is not None else "—"
        md.append("| " + c["name"] + " | " + c["subtype"] + " | " + t + " | " +
                  pv + " | " + rule_str + " | " + tight + " |")

md.append("")
md.append("## Interventions")
md.append("")
for c in tax["classes"]:
    if "rule_only_intervention" in c["evidence"]:
        r = c["evidence"]["rule_only_intervention"]
        md.append("**" + c["subtype"] + " — rule-only prompt:**")
        md.append("")
        md.append("> " + r["prompt"])
        md.append("")
        md.append("Result: " + str(r["n_passed"]) + "/" + str(r["n"]) +
                  " = " + str(r["pass_valid"]) + "  CI95 " + str(r["ci95"]))
        md.append("")
        md.append("_" + r["note"] + "_")
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
print("Systematic subtype — rule-only intervention: 20/20 = 1.00  CI95 [0.84, 1.00]")
print("Stochastic subtype  — explicit abs_tol default:  9/9 = 1.00")
print("Wrote TAXONOMY.md")
