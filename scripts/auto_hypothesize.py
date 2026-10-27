#!/usr/bin/env python3
"""Autonomous hypothesis generation. Excludes features that tautologically
overlap the fail criterion; keeps only features about the GOAL, REASONING,
or PLAN STRUCTURE (not the emitted content)."""
import argparse, json, pathlib, sys
from collections import defaultdict
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from verifier_deterministic import TEMPLATE_RE

def load(p): return [json.loads(l) for l in pathlib.Path(p).read_text().splitlines() if l.strip()]

def fail(r):
    c = r.get("content") or ""
    return bool(TEMPLATE_RE.search(c)) or r.get("class") in ("placeholder","no_write")

def features(r):
    """All features are observations that do NOT look at emitted content.
    The point: predict failure without seeing what the model wrote."""
    plan = {}
    try: plan = json.loads(r.get("plan_raw") or "{}")
    except Exception: pass
    steps = plan.get("steps", [])
    rl = r.get("reasoning_len", 0)
    goal = (r.get("goal") or "").lower()
    reasoning = (r.get("reasoning") or "").lower()
    titles = " ".join(s.get("title","") for s in steps).lower()
    depth = 0
    for s in steps:
        if s.get("depends_on"): depth = max(depth, 1)
    return {
        "reasoning_len": "short" if rl < 100 else "medium" if rl < 150 else "long",
        "reasoning_mentions_read": "read" in reasoning,
        "reasoning_mentions_write": "write" in reasoning,
        "goal_mentions_contents": "contents" in goal,
        "goal_mentions_read_write": "read" in goal and "write" in goal,
        "goal_word_count": "short" if len(goal.split()) < 10 else "long",
        "plan_title_mentions_answer": "answer" in titles,
        "plan_has_depends_on": depth > 0,
        "plan_step_count_bucket": "2" if len(steps) == 2 else "3" if len(steps) == 3 else "4+" if len(steps) >= 4 else "0-1",
        "reasoning_mentions_step": "step" in reasoning,
        "reasoning_mentions_plan": "plan" in reasoning,
    }

def scan(rows, feature_name):
    """Stratified by bench. Only within-bench variance counts."""
    by = defaultdict(lambda: {"n":0, "fail":0})
    for r in rows:
        v = features(r)[feature_name]
        key = "true" if v is True else "false" if v is False else str(v)
        by[key]["n"] += 1; by[key]["fail"] += int(fail(r))
    return {k: {"n": v["n"], "fail": v["fail"],
                "rate": v["fail"]/v["n"] if v["n"] else 0} for k,v in by.items()}

def scan_stratified(rows, feature_name):
    """Compute lift WITHIN each bench, then average. Excludes between-bench confounds."""
    benches = defaultdict(list)
    for r in rows: benches[r.get("cond","?") if False else
                        ("seed" if "seed" in str(r.get("item","")) else
                         "test" if "fam14" in str(r.get("item","")) else "other")].append(r)
    lifts = []
    for bench, rs in benches.items():
        if len(rs) < 4: continue
        st = scan(rs, feature_name)
        if len(st) < 2: continue
        vals = list(st.values())
        if min(v["n"] for v in vals) < 2: continue
        lift = max(v["rate"] for v in vals) - min(v["rate"] for v in vals)
        lifts.append({"bench": bench, "lift": lift, "split": st})
    if len(lifts) < 2: return None
    return {"mean_lift": sum(l["lift"] for l in lifts)/len(lifts),
            "per_bench": lifts}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--traces", nargs="+",
                    default=["artifacts/traces/trace_seed.jsonl",
                             "artifacts/traces/trace_test.jsonl"])
    ap.add_argument("--out", default="results/H009_auto.json")
    a = ap.parse_args()
    rows = []
    for p in a.traces: rows += load(p)
    print(f"[auto] {len(rows)} rows from {len(a.traces)} files")
    base = sum(fail(r) for r in rows) / len(rows)
    print(f"[auto] baseline fail rate: {base:.3f}\n")

    candidates = []
    for fname in list(features(rows[0]).keys()):
        st_strat = scan_stratified(rows, fname)
        if st_strat is None: continue
        stats = st_strat['per_bench'][0]['split']  # keep shape
        lift = st_strat['mean_lift']
        if len(stats) < 2: continue
        vals = list(stats.values())
        if min(v["n"] for v in vals) < 3: continue    # need 3+ support per arm
        lift = max(v["rate"] for v in vals) - min(v["rate"] for v in vals)
        candidates.append({"feature": fname, "split": stats, "lift": lift,
                            "min_support": min(v["n"] for v in vals)})

    candidates.sort(key=lambda x: (x["lift"], x["min_support"]), reverse=True)
    print("=== candidate hypotheses (independent of emitted content) ===")
    for c in candidates[:5]:
        hi = max(c["split"].items(), key=lambda kv: kv[1]["rate"])
        lo = min(c["split"].items(), key=lambda kv: kv[1]["rate"])
        print(f"\n{c['feature']}  lift={c['lift']:+.3f}  min_support={c['min_support']}")
        for k, v in sorted(c["split"].items(), key=lambda kv: -kv[1]["rate"]):
            print(f"  {k:8s}  n={v['n']:<3d}  fail={v['fail']:<3d}  rate={v['rate']:.3f}")
        print(f"  -> HYPOTHESIS: '{c['feature']}={hi[0]}' fail {hi[1]['rate']:.2f} vs {lo[1]['rate']:.2f}")

    out = pathlib.Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"baseline_rate": base, "n": len(rows), "candidates": candidates[:5]}, indent=2))
    print(f"\n-> {out}")

    if candidates:
        top = candidates[0]
        print(f"\n=== strongest hypothesis for next session ===")
        print(f"{top['feature']}  (lift {top['lift']:+.3f}, min_support {top['min_support']})")
        print(f"Register as prospective H010 before observing held-out result.")

if __name__ == "__main__":
    main()
