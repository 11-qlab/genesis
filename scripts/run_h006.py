#!/usr/bin/env python3
"""H006 — per-condition placeholder rate on trace_test.jsonl."""
import argparse, json, pathlib

def main():
    ap = argparse.ArgumentParser(description="H006 per-cond placeholder rate")
    ap.add_argument("--trajectories", default="artifacts/traces/trace_test.jsonl")
    ap.add_argument("--out", default="results/H006.json")
    a = ap.parse_args()

    rows = [json.loads(l) for l in pathlib.Path(a.trajectories).read_text().splitlines() if l.strip()]
    by_cond = {}
    for r in rows:
        by_cond.setdefault(r.get("cond", "?"), []).append(r)

    out = {"id": "H006", "per_cond": {}, "pooled_rate": None}
    total_ph = 0
    for cond, rs in by_cond.items():
        ph = sum(1 for r in rs if r.get("class") == "placeholder")
        nw = sum(1 for r in rs if r.get("class") == "no_write")
        total_ph += ph
        out["per_cond"][cond] = {"n": len(rs), "placeholder": ph, "no_write": nw,
                                  "fail": ph + nw, "fail_rate": (ph+nw)/len(rs)}
    out["pooled_rate"] = total_ph / len(rows)
    rates = [v["fail_rate"] for v in out["per_cond"].values()]
    out["spread"] = max(rates) - min(rates) if len(rates) > 1 else 0.0
    out["verdict"] = "PASS" if out["spread"] > 0.05 else "REJECTED"
    out["verdict_rule"] = "PASS if per-cond fail rate spread > 0.05"

    pathlib.Path(a.out).write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))

if __name__ == "__main__":
    main()
