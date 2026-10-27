#!/usr/bin/env python3
"""Per-defect sensitivity ablation against committed trace format.

Schema: each row has plan_raw (stringified JSON) and content (emitted write).
Mutants operate on the parsed plan, then re-serialize as plan_raw.
"""
import argparse, json, pathlib, sys

def _parse_plan(row):
    try:
        return json.loads(row.get("plan_raw") or "{}")
    except Exception:
        return {}

def _serialize(row, plan):
    r = json.loads(json.dumps(row))     # deep copy
    r["plan_raw"] = json.dumps(plan)
    return r

def defect_drop_write_content(row):
    plan = _parse_plan(row)
    for s in plan.get("steps", []):
        if s.get("tool") == "fs_write":
            s.get("args", {}).pop("content", None)
    return _serialize(row, plan)

def defect_self_pair(row):
    """Defect 4: pair item with itself (A/B discrimination becomes noise)."""
    r = json.loads(json.dumps(row))
    if r.get("expected") is not None:
        r["expected"] = r.get("content")
    return r

def defect_truncate_obs(row, n=32):
    """Defect 2: truncate observations at first read in plan."""
    plan = _parse_plan(row)
    for s in plan.get("steps", []):
        if s.get("tool") == "fs_read":
            args = s.get("args", {})
            args["max_bytes"] = min(args.get("max_bytes", n), n)
    return _serialize(row, plan)

MUTANTS = {
    "drop_write_content": defect_drop_write_content,
    "self_pair":          defect_self_pair,
    "truncate_obs":       defect_truncate_obs,
}

def _extract_fail(verdict):
    """verify() returns ('LABEL', 'reason', meta). Fail = LABEL not in ('CORRECT','OK')."""
    if isinstance(verdict, tuple) and len(verdict) >= 1:
        return verdict[0] not in ("CORRECT", "OK", "PASS")
    if isinstance(verdict, dict):
        return bool(verdict.get("fail") or verdict.get("flag"))
    return bool(verdict)

def main():
    ap = argparse.ArgumentParser(description="Per-defect sensitivity ablation")
    ap.add_argument("--trajectories", default="artifacts/traces/trace_test.jsonl")
    ap.add_argument("--out", default="artifacts/esf/masking_ablation.json")
    a = ap.parse_args()

    sys.path.insert(0, str(pathlib.Path(__file__).parent))
    from verifier_deterministic import verify

    src = [json.loads(l) for l in pathlib.Path(a.trajectories).read_text().splitlines() if l.strip()]
    print(f"[ablate] {len(src)} base trajectories from {a.trajectories}")

    def flag_rate(rows):
        if not rows: return 0.0
        return sum(_extract_fail(verify(r)) for r in rows) / len(rows)

    base = flag_rate(src)
    results = {"file": a.trajectories, "n": len(src),
               "baseline": {"flag_rate": base}, "mutants": {}}
    print(f"[ablate] baseline flag rate: {base:.3f}")
    for name, fn in MUTANTS.items():
        mut = [fn(r) for r in src]
        rate = flag_rate(mut)
        results["mutants"][name] = {"flag_rate": rate, "delta": rate - base}
        print(f"[ablate] {name:20s} flag_rate={rate:.3f}  delta={rate-base:+.3f}")

    pathlib.Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(a.out).write_text(json.dumps(results, indent=2))
    print(f"[ablate] -> {a.out}")

if __name__ == "__main__":
    main()
