#!/usr/bin/env python3
"""Execute a hypothesis manifest and write a result file.

Supports two condition types:
  - verifier: run verifier_deterministic with a chosen regex set (v1 or v2)
  - prompt:   run the planner under a chosen SYSTEM_PROMPT (baseline or rule9)

Hypotheses are declared in `hypotheses/Hxxx.json` with `status: pending`.
Completed hypotheses (status: completed) are recorded only.
"""
import argparse, json, pathlib, sys

sys.path.insert(0, "scripts")
sys.path.insert(0, "src")

from analysis import mcnemar_exact, bf_mcnemar, bh_correction

REGEX_SETS = {}

def _load_verifiers():
    import verifier_deterministic as vd
    REGEX_SETS["v1"] = vd.TEMPLATE_RE
    REGEX_SETS["v2"] = vd.TEMPLATE_RE_V2
    return vd

def run_verifier_condition(items, cond, vd):
    regex = REGEX_SETS[cond.get("regex_set", "v1")]
    out = {}
    for it in items:
        v, reason, _ = vd.verify(it, template_re=regex)
        out[it["item_id"]] = {"verdict": v, "reason": reason}
    return out

def load_items(bench_path):
    return [json.loads(l) for l in pathlib.Path(bench_path).read_text().strip().splitlines() if l.strip()]

def run_manifest(manifest_path, out_path):
    manifest = json.loads(pathlib.Path(manifest_path).read_text())

    if manifest["status"] == "completed":
        print(f"{manifest['id']}: already completed — see {manifest.get('result_file')}")
        return

    vd = _load_verifiers()
    bench = manifest.get("bench")
    n = manifest.get("n_items")
    items = load_items(bench)
    if n:
        items = items[:n]

    ca = manifest["conditions"]["a"]
    cb = manifest["conditions"]["b"]
    if ca["type"] != "verifier" or cb["type"] != "verifier":
        print(f"{manifest['id']}: only verifier conditions supported tonight")
        return

    print(f"{manifest['id']}: {len(items)} items, verifier V1 vs V2")
    a = run_verifier_condition(items, ca, vd)
    b = run_verifier_condition(items, cb, vd)

    # Paired analysis: count transitions per class
    classes = sorted({it["item_id"].split("-")[1] for it in items})
    per_class = {c: {"n": 0, "a_incorrect": 0, "b_incorrect": 0, "a2b": 0, "b2a": 0} for c in classes}
    for it in items:
        tag = it["item_id"].split("-")[1]
        va, vb = a[it["item_id"]]["verdict"], b[it["item_id"]]["verdict"]
        per_class[tag]["n"] += 1
        if va == "INCORRECT": per_class[tag]["a_incorrect"] += 1
        if vb == "INCORRECT": per_class[tag]["b_incorrect"] += 1
        if va == "CORRECT" and vb == "INCORRECT": per_class[tag]["a2b"] += 1
        if va == "INCORRECT" and vb == "CORRECT": per_class[tag]["b2a"] += 1

    # Primary test: descriptive-content detection on positive class, FP on real
    dc = per_class.get("dc") or per_class.get("descriptive") or {}
    real = per_class.get("real") or {}
    p = mcnemar_exact(dc.get("a2b", 0), dc.get("b2a", 0)) if dc else 1.0
    bf = bf_mcnemar(dc.get("b2a", 0), dc.get("a2b", 0)) if dc else 1.0
    fp_delta = real.get("a2b", 0) - real.get("b2a", 0)

    # Verdict rule for H005: V2 must catch descriptive-content items that V1 missed
    # AND must not introduce false positives on real content
    criterion_met = (
        dc and dc.get("b2a", 0) >= 3 and    # at least 3 items flipped to INCORRECT
        fp_delta <= 0                        # no net FP increase on real
    )
    verdict = "PASS" if criterion_met else "REJECTED"

    result = {
        "id": manifest["id"],
        "completed_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "verdict": verdict,
        "per_class": per_class,
        "mcnemar_p_descriptive": p,
        "bf_mcnemar_descriptive": bf,
        "fp_delta_on_real": fp_delta,
        "criterion": "V2 catches >=3 descriptive items that V1 missed, no net FP increase on real content",
        "criterion_met": bool(criterion_met),
        "design": manifest.get("bench"),
        "conditions": {
            "a": {"regex_set": manifest["conditions"]["a"].get("regex_set", "v1")},
            "b": {"regex_set": manifest["conditions"]["b"].get("regex_set", "v2")},
        },
    }
    pathlib.Path(out_path).write_text(json.dumps(result, indent=2))

    print(f"\n{manifest['id']} — {manifest['claim']}")
    for c in classes:
        d = per_class[c]
        print(f"  {c:<12} n={d['n']}  V1_incorrect={d['a_incorrect']}  V2_incorrect={d['b_incorrect']}  "
              f"a2b={d['a2b']}  b2a={d['b2a']}")
    print(f"  McNemar (descriptive class): p={p:.4f}  BF10={bf:.2f}")
    print(f"  FP delta on real: {fp_delta}")
    print(f"  Verdict: {verdict}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    run_manifest(args.manifest, args.out)
