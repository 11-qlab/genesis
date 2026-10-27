#!/usr/bin/env python3
"""Re-introduce each recording-layer defect individually against a fixed
trajectory set; measure verifier sensitivity drop per defect."""
import argparse, json, pathlib

# FILL: each mutant takes a trajectory dict, returns a mutated copy that
# reproduces defect N. Replace bodies with your actual defect logic.
def defect_drop_tool_args(t):
    t = json.loads(json.dumps(t))
    for s in t.get("steps", []):
        if s.get("tool") == "fs_write":
            s.get("args", {}).pop("content", None)
    return t

def defect_self_pair(t):
    t = json.loads(json.dumps(t))
    for s in t.get("steps", []):
        if s.get("tool") in ("fs_read", "fs_write"):
            s["target"] = s.get("target", "self")   # FILL
    return t

def defect_truncate_obs(t, n=32):
    t = json.loads(json.dumps(t))
    for s in t.get("steps", []):
        if s.get("tool") == "fs_read" and "observation" in s.get("result", {}):
            s["result"]["observation"] = s["result"]["observation"][:n]
    return t

MUTANTS = {
    "drop_tool_args": defect_drop_tool_args,
    "self_pair":      defect_self_pair,
    "truncate_obs":   defect_truncate_obs,
}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trajectories", required=True)
    ap.add_argument("--out", default="/tmp/masking_ablation.json")
    a = ap.parse_args()
    src = [json.loads(l) for l in pathlib.Path(a.trajectories).read_text().splitlines() if l.strip()]
    print(f"[ablate] {len(src)} base trajectories")

    import sys
    sys.path.insert(0, "scripts")
    try:
        from verifier_deterministic import extract_reads as verify  # FILL: actual import
    except Exception as e:
        sys.exit(f"PROBE FAIL: cannot import verifier ({e}). "
                 "Point this at the callable used by scripts/verifier_deterministic.py")

    base_rate = sum(bool(verify(t)) for t in src) / len(src)
    results = {"baseline": {"flag_rate": base_rate, "n": len(src)}, "mutants": {}}
    print(f"[ablate] baseline flag rate: {base_rate:.3f}")
    for name, fn in MUTANTS.items():
        mut = [fn(t) for t in src]
        rate = sum(bool(verify(t)) for t in mut) / len(mut)
        results["mutants"][name] = {"flag_rate": rate, "delta": rate - base_rate}
        print(f"[ablate] {name:16s} flag_rate={rate:.3f} delta={rate-base_rate:+.3f}")
    pathlib.Path(a.out).write_text(json.dumps(results, indent=2))
    print(f"[ablate] -> {a.out}")

if __name__ == "__main__":
    main()
