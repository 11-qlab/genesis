#!/usr/bin/env python3
"""60_attribute_failures.py — route each anomaly to an intervention level.

Not reflection. Not freeform. Each anomaly gets a hypothesis set, each
hypothesis is scored against evidence, top-scoring wins. SAGE's mechanism.

Levels: capability_limit / harness_class / class_wrong / template_wrong /
        implementation_broken / infra / design_wrong
"""
import importlib, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent
OUT  = ROOT / "state" / "attribution.jsonl"
ar   = importlib.import_module("autonomous_research")
tax  = json.loads((ROOT/"taxonomy.json").read_text())
classes = {c["name"]+"/"+c["subtype"] for c in tax.get("classes",[])}

HYPOTHESES = {
    "unclassified_class":       ["harness_class", "class_wrong", "capability_limit"],
    "candidate_invalid":        ["capability_limit", "implementation_broken", "infra", "template_wrong"],
    "contaminated_run":         ["infra", "template_wrong", "implementation_broken"],
    "skip_generation_failed":   ["capability_limit", "template_wrong", "infra"],
    "skip_no_plan":             ["infra", "design_wrong"],
    "zero_valid":               ["template_wrong", "infra"],
    "unknown_experiment_type":  ["design_wrong"],
}

def score(h, a):
    kind = a.get("kind",""); cls = a.get("class","")
    reason = ((a.get("validation_reason") or "") + " " +
              (a.get("gap_reason") or "") + " " +
              (a.get("value") or "")).lower()
    if h == "capability_limit":
        impl = ar._known_correct_for(cls, {})() if cls else ""
        return 1.0 if not impl else 0.0
    if h == "harness_class":
        return 1.0 if cls and (cls.startswith(("test_gap_","harness_","synthetic_"))
                               or "_test_" in cls) else 0.0
    if h == "class_wrong":
        return 1.0 if cls and cls not in classes else 0.0
    if h == "implementation_broken":
        return 1.0 if (reason.strip().endswith(":") or "traceback" in reason
                       or "crash" in reason) else 0.0
    if h == "infra":
        # contaminated_run means infra>valid -> infra failure by definition
        if kind == "contaminated_run": return 1.0
        if any(k in reason for k in ("rate limit","timeout","connection",
                                     "network","429","503","backend","abort")): return 1.0
        return 0.0
    if h == "template_wrong":
        if kind == "zero_valid" and a.get("valid",1) == 0: return 1.0
        return 0.0
    if h == "design_wrong":
        return 0.5   # default suspicion when nothing else fits
    return 0.0

rows = []
for line in (ROOT/"state"/"anomalies.jsonl").read_text().splitlines():
    if not line.strip(): continue
    a = json.loads(line)
    hyps = HYPOTHESES.get(a["kind"], ["design_wrong"])
    scored = sorted(((score(h,a), h) for h in hyps), reverse=True)
    best_score, best = scored[0]
    rows.append({**a, "attribution": best, "confidence": best_score,
                 "alternatives": [{"h": h, "s": s} for s, h in scored[1:] if s > 0]})

OUT.write_text("\n".join(json.dumps(r, sort_keys=True) for r in rows) + "\n")
from collections import Counter
c = Counter(r["attribution"] for r in rows)
print(f"{'LINE':<6} {'KIND':<24} {'ATTRIBUTION':<24} {'CONF'}")
print("─"*80)
for r in rows:
    print(f"{r['line']:<6} {r['kind']:<24} {r['attribution']:<24} {r['confidence']:.1f}")
print(f"\n-> {OUT}")
print("\nBy level:")
for k,n in c.most_common(): print(f"  {k:<24} {n}")
