import json, datetime
from pathlib import Path

tax = json.load(open("taxonomy.json"))

# Update generated timestamp
tax["generated"] = datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z")
tax["version"] = "1.1"

# Locate the stochastic class and record the pooled estimate
for cls in tax["classes"]:
    if cls["name"] != "prior_override_failure":
        continue
    if cls["subtype"] != "stochastic":
        continue

    # Pooled: earlier 4/9 + new 28/40
    ev = cls["evidence"]
    ev["affected_models"]["openai/gpt-oss-120b"]["sample_1"] = {
        "n": 9, "passed": 4,
        "source": "research_robust.py (3 rounds x 3 trials)",
    }
    ev["affected_models"]["openai/gpt-oss-120b"]["sample_2"] = {
        "n": 40, "passed": 28,
        "source": "tighten_rate.py (single 40-trial run)",
    }

    passed = 4 + 28
    total  = 9 + 40
    p = passed / total
    # Wilson 95% CI
    z = 1.96
    denom = 1 + z*z/total
    center = (p + z*z/(2*total)) / denom
    half = (z * ((p*(1-p) + z*z/(4*total)) ** 0.5) / (total ** 0.5)) / denom
    lo, hi = max(0.0, center - half), min(1.0, center + half)

    ev["affected_models"]["openai/gpt-oss-120b"]["n"] = total
    ev["affected_models"]["openai/gpt-oss-120b"]["n_valid"] = total
    ev["affected_models"]["openai/gpt-oss-120b"]["n_passed"] = passed
    ev["affected_models"]["openai/gpt-oss-120b"]["pass_valid"] = round(p, 3)
    ev["affected_models"]["openai/gpt-oss-120b"]["ci95"] = [round(lo, 3), round(hi, 3)]
    ev["affected_models"]["openai/gpt-oss-120b"]["pass_all"] = round(p, 3)

    cls["signature"] = (
        "~65% pass rate (pooled N=49, 95% CI ["
        + str(round(lo, 2)) + ", " + str(round(hi, 2))
        + "]) on spec-divergent task; 100% after explicit abs_tol specification"
    )

tax["revision_note"] = (
    "v1.1: stochastic rate revised from 0.444 (N=9) to 0.653 (pooled N=49) after "
    "tighten_rate.py produced 28/40. The mechanism is unchanged; only the magnitude."
)

# Update inverse-scaling statement with corrected number
tax["finding_inverse_scaling"]["evidence"] = (
    "approximately_equal / original — pooled: 120b 32/49 (~65%); "
    "qwen 18/18 (100%); 20b 18/18 (100%). Inverse-scaling holds: "
    "the model with the strongest coding priors fails most often."
)

Path("taxonomy.json").write_text(json.dumps(tax, indent=2))

# Regenerate TAXONOMY.md
md = ["# Failure Taxonomy", "", "Version " + tax["version"] + " — generated " + tax["generated"], ""]
md.append("## Classes")
md.append("")
md.append("| Class | Subtype | Task | Pass rate (original) | Pass rate (tightened) |")
md.append("|---|---|---|---|---|")
for c in tax["classes"]:
    t = c["evidence"]["task"]
    for m, ev in c["evidence"]["affected_models"].items():
        ci = ev.get("ci95")
        pv = str(ev["pass_valid"]) if "pass_valid" in ev else "n/a"
        pv_str = pv + (" (95% CI " + str(ci) + ")" if ci else "")
        tight = c["evidence"]["tightened"]["pass_valid"]
        md.append("| " + c["name"] + " | " + c["subtype"] + " | " + t + " | " +
                  pv_str + " | " + str(tight) + " |")
md.append("")
md.append("## Control")
md.append(tax["control"]["model"] + " — " + tax["control"]["result"] + ". " + tax["control"]["interpretation"])
md.append("")
md.append("## Inverse-scaling finding")
md.append(tax["finding_inverse_scaling"]["statement"])
md.append("")
md.append("Evidence: " + tax["finding_inverse_scaling"]["evidence"])
md.append("")
if "revision_note" in tax:
    md.append("## Revision note")
    md.append(tax["revision_note"])
    md.append("")

Path("TAXONOMY.md").write_text("\n".join(md))

print("Updated taxonomy.json -> v" + tax["version"])
print("Stochastic class: pooled " + str(passed) + "/" + str(total) +
      " = " + str(round(p, 3)) +
      "  CI95 = [" + str(round(lo, 3)) + ", " + str(round(hi, 3)) + "]")
print("Wrote TAXONOMY.md")
