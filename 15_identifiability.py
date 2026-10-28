#!/usr/bin/env python3
"""15_identifiability.py — before generating, check whether the observation
protocol can in principle resolve the class's question.

Each class declares:
  required_observables  what the eval harness must be able to measure
  wired_into            which harness functions provide them
  min_n_statistical     what sample size gives power
  min_n_achievable      what rate limits permit per session

Verdicts:
  resolvable           all observables wired, achievable N >= statistical
  certified_exhausted  observables wired but achievable < statistical at current infra
  capability_limit     required observable not in harness
  undeclared           class not in map -> refuse to generate
"""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent
OUT  = ROOT / "state" / "identifiability.jsonl"
tax  = json.loads((ROOT/"taxonomy.json").read_text())

# Declared by the human. NOT auto-generated. This IS the identifiability check.
IDENTIFIABILITY = {
    "prior_override_failure/systematic": {
        "required_observables": ["pass_rate_ambiguous","pass_rate_tightened"],
        "wired_into": ["trial","update"],
        "min_n_statistical": 20, "min_n_achievable": 15,
    },
    "prior_override_failure/stochastic": {
        "required_observables": ["pass_rate_ambiguous"],
        "wired_into": ["trial","update"],
        "min_n_statistical": 20, "min_n_achievable": 15,
    },
    "prior_override_failure/function_name_trigger": {
        "required_observables": ["name_contrast"],
        "wired_into": ["trial"],
        "min_n_statistical": 10, "min_n_achievable": 10,
    },
}

# What the harness actually provides. Update when harness changes.
HARNESS_PROVIDES = {"pass_rate_ambiguous","pass_rate_tightened","name_contrast"}

rows = []
for cls in tax.get("classes", []):
    key = cls["name"] + "/" + cls["subtype"]
    decl = IDENTIFIABILITY.get(key)
    if not decl:
        rows.append({"class": key, "verdict": "undeclared",
                     "reason": "no identifiability declaration -> refuse to generate"}); continue
    missing_obs = [o for o in decl["required_observables"] if o not in HARNESS_PROVIDES]
    if missing_obs:
        rows.append({"class": key, "verdict": "capability_limit",
                     "reason": f"observable not in harness: {missing_obs}"}); continue
    if decl["min_n_achievable"] < decl["min_n_statistical"]:
        rows.append({"class": key, "verdict": "certified_exhausted",
                     "reason": f"need N>={decl['min_n_statistical']}, rate limit permits "
                               f"N={decl['min_n_achievable']} -> raise limit or reduce class"}); continue
    rows.append({"class": key, "verdict": "resolvable",
                 "reason": "all observables wired; achievable N sufficient"})

OUT.write_text("\n".join(json.dumps(r, sort_keys=True) for r in rows) + "\n")
for r in rows: print(f"  {r['verdict']:<22} {r['class']:<44} {r['reason']}")
print(f"\n-> {OUT}")

# Refuse gate: if any class is undeclared, block generation for that class.
undeclared = [r["class"] for r in rows if r["verdict"] == "undeclared"]
if undeclared:
    print(f"\n[BLOCK] generate_candidate() must refuse these classes until declared:")
    for u in undeclared: print(f"  - {u}")
