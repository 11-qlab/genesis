#!/usr/bin/env python3
"""Execute H006 exactly as registered. No re-runs, no tuning."""
import json, pathlib, subprocess, sys
H = json.loads(pathlib.Path("hypotheses/H006.json").read_text())
print(f"[H006] {H['claim'][:80]}...")

# Run verifier A (deterministic)
subprocess.run([sys.executable, "scripts/verifier_deterministic.py",
    "--trajectories", "artifacts/traces/trace_test.jsonl",
    "--out", "/tmp/h006_a.json"], check=True)
subprocess.run([sys.executable, "scripts/provenance_verifier.py",
    "--trajectories", "artifacts/traces/trace_test.jsonl",
    "--out", "/tmp/h006_b.json"], check=True)

a = json.loads(pathlib.Path("/tmp/h006_a.json").read_text())
b = json.loads(pathlib.Path("/tmp/h006_b.json").read_text())
a_fail = {r.get("task_id") or r.get("id") for r in a
          if r.get("verdict") in ("FAIL", False) or r.get("fail") is True}
b_fail = {r["task_id"] for r in b if r["fail"]}
only_b = b_fail - a_fail
only_a = a_fail - b_fail
n = len(only_a) + len(only_b)
# McNemar exact
from math import comb
p = 1.0 if n == 0 else min(1.0, 2 * sum(comb(n, k) for k in range(0, min(len(only_a), len(only_b))+1)) / 2**n)
verdict = "PASS" if len(only_b) > len(only_a) and p < 0.05 else "REJECTED"
out = {"id": "H006", "verdict": verdict,
       "n_a_fail": len(a_fail), "n_b_fail": len(b_fail),
       "b_only": sorted(only_b), "a_only": sorted(only_a),
       "mcnemar_p": p}
pathlib.Path("results/H006.json").write_text(json.dumps(out, indent=2))
print(json.dumps(out, indent=2))
