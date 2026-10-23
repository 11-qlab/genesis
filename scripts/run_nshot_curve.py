#!/usr/bin/env python3
"""
N-shot learning curve: run a bench at n_shots ∈ {0,1,3,5} by prepending
k seed examples to each goal.

Usage:
    python3 scripts/run_nshot_curve.py \
        --bench bench/error_recovery.jsonl \
        --seed-file bench/families/seed/fam07.jsonl \
        --out artifacts/nshot_curve_er.json

Output: per-n accuracy, JSON + table.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_seed(path: Path) -> list[dict]:
    out = []
    with path.open() as f:
        for line in f:
            if line.strip():
                out.append(json.loads(line))
    return out


def augment_bench(bench: Path, seeds: list[dict], k: int, out_path: Path) -> None:
    prefix = ""
    if k > 0 and seeds:
        prefix = f"Here are {k} examples of similar tasks:\n"
        for i, ex in enumerate(seeds[:k], 1):
            goal = ex.get("goal", "")
            seq = ex.get("expect_subsequence") or [ex.get("expect_tool") or "fs_read"]
            prefix += f"\nExample {i}: {goal}\nPlan tools: {seq}\n"
        prefix += "\nNow plan the following: "

    with bench.open() as f_in, out_path.open("w") as f_out:
        for line in f_in:
            if not line.strip():
                continue
            it = json.loads(line)
            it["goal"] = prefix + it.get("goal", "")
            f_out.write(json.dumps(it) + "\n")


def run_one(bench_aug: Path, tag: str, delay_ms: int = 1500) -> dict | None:
    db = f"/tmp/agi_nshot_{tag}.sqlite3"
    ws = f"/tmp/agi_nshot_{tag}_ws"
    for p in (db,):
        with contextlib.suppress(FileNotFoundError): os.remove(p)
    shutil.rmtree(ws, ignore_errors=True)

    env = {
        **os.environ,
        "AGI_STORAGE_PATH": db,
        "AGI_FS_ROOT": ws,
        "PYTHONPATH": "src",
    }
    args = [sys.executable, "-m", "agi", "eval", "run",
            "--bench", str(bench_aug), "--seed", "all",
            "--strategy", "greedy", "--delay-ms", str(delay_ms)]
    try:
        p = subprocess.run(args, cwd=ROOT, env=env,
                           capture_output=True, text=True, timeout=1800)
        return json.loads(p.stdout)
    except Exception as e:
        print(f"  [!] {tag}: {type(e).__name__}: {e}", file=sys.stderr)
        return None
    finally:
        with contextlib.suppress(FileNotFoundError): os.remove(db)
        shutil.rmtree(ws, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bench", required=True)
    ap.add_argument("--seed-file", required=True)
    ap.add_argument("--n-values", default="0,1,3,5")
    ap.add_argument("--out", required=True)
    ap.add_argument("--delay-ms", type=int, default=1500)
    args = ap.parse_args()

    os.chdir(ROOT)
    bench = Path(args.bench)
    seed_file = Path(args.seed_file)
    seeds = load_seed(seed_file)
    n_values = [int(x) for x in args.n_values.split(",")]

    max_k = min(len(seeds), max(n_values))
    n_values = [n for n in n_values if n <= max_k]

    results = {}
    for n in n_values:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl",
                                         delete=False) as tmp:
            aug = Path(tmp.name)
        augment_bench(bench, seeds, n, aug)
        print(f"  n={n}: running ...", flush=True)
        d = run_one(aug, tag=f"n{n}", delay_ms=args.delay_ms)
        with contextlib.suppress(FileNotFoundError): os.remove(aug)
        if d is None:
            print("    FAILED"); continue
        results[n] = {"passed": d["passed"], "total": d["total"],
                       "accuracy": d["accuracy"]}
        print(f"    {d['passed']}/{d['total']} = {d['accuracy']:.3f}")

    if len(results) < 2:
        print("  need ≥2 successful runs to fit a curve"); return

    import math
    xs = [math.log(max(n, 1)) for n in results]
    ys = [results[n]["accuracy"] for n in results]
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=False))
    den = sum((x - mean_x) ** 2 for x in xs) or 1e-9
    slope = num / den

    print(f"\n  fitted slope (accuracy per log(n+1)): {slope:+.3f}")
    if slope < 0.05:
        verdict = "narrow: <0.05, needs many examples"
    elif slope < 0.15:
        verdict = "moderate: 0.05-0.15, some in-context learning"
    else:
        verdict = "general: >0.15, few examples flip accuracy"
    print(f"  verdict: {verdict}")

    out = Path(args.out)
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({
        "bench": args.bench, "seed_file": args.seed_file,
        "results": results, "slope": slope, "verdict": verdict,
    }, indent=2))
    print(f"\n  wrote {out}")


if __name__ == "__main__":
    main()
