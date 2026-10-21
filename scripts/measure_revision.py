#!/usr/bin/env python3
"""T13 — plan revision vs single-plan baseline.

Both conditions run through `agi eval run --seed all` so the workspace
is seeded per-item, isolated per-run, and contamination is detected.
No reimplementation of the runner loop.
"""
from __future__ import annotations

import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)

STRATEGIES = [
    ("baseline (greedy)", ["--strategy", "greedy"]),
    ("revision (1 attempt)", ["--strategy", "revision"]),
]


def run(strategy_flags):
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.join(REPO, "src")
    env["AGI_STORAGE_PATH"] = f"/tmp/agi_rev_{os.getpid()}.sqlite3"
    env["AGI_FS_ROOT"] = f"/tmp/agi_rev_{os.getpid()}_ws"
    os.makedirs(env["AGI_FS_ROOT"], exist_ok=True)
    cmd = [
        sys.executable, "-m", "agi", "eval", "run",
        "--bench", "bench/task_chain.jsonl",
        "--seed", "all",
        "--delay-ms", "2000",
    ] + strategy_flags
    r = subprocess.run(cmd, env=env, capture_output=True, text=True)
    import json
    try:
        return json.loads(r.stdout)
    except Exception:
        print(f"could not parse output for {strategy_flags}: {r.stdout[:300]}")
        return None


def main() -> int:
    results = {}
    for label, flags in STRATEGIES:
        print(f"\n=== {label} ===")
        data = run(flags)
        if data is None:
            results[label] = None
            continue
        results[label] = {
            "accuracy": data.get("accuracy"),
            "passed": data.get("passed"),
            "total": data.get("total"),
            "contaminated": data.get("contaminated"),
            "rate_limited": data.get("rate_limited_items"),
            "strategy": data.get("strategy"),
        }
        print(f"  accuracy:       {data.get('accuracy')}")
        print(f"  passed:         {data.get('passed')}/{data.get('total')}")
        print(f"  contaminated:   {data.get('contaminated')}")
        print(f"  rate_limited:   {data.get('rate_limited_items')}")

    print("\n" + "=" * 55)
    print(f"{'condition':<22} {'passed':>6} {'total':>6} {'accuracy':>9}")
    print("-" * 55)
    for label, _ in STRATEGIES:
        r = results.get(label)
        if r is None:
            print(f"{label:<22} {'?':>6} {'?':>6} {'?':>9}")
            continue
        print(f"{label:<22} {r['passed']:>6} {r['total']:>6} {r['accuracy']:>9.4f}")

    b = results.get("baseline (greedy)")
    v = results.get("revision (1 attempt)")
    if b and v:
        delta = v["passed"] - b["passed"]
        print()
        print(f"delta: {delta:+d} items, {(v['accuracy'] - b['accuracy']):+.4f} accuracy")
        if b["contaminated"] or v["contaminated"]:
            print("WARNING: one or both conditions contaminated. Result is not usable.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
