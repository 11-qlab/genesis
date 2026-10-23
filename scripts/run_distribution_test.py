#!/usr/bin/env python3
"""
Distribution test: run all families N times, compute mutual information
between family identity and pass/fail.

    I(family; pass) = H(pass) - H(pass | family)

Low I → scattered failures → possible general mechanism
High I → clustered failures → narrow agent

Usage:
    python3 scripts/run_distribution_test.py --runs 3 --out artifacts/mi_test.json
"""
from __future__ import annotations

import argparse
import contextlib
import json
import math
import os
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAMILY_DIR = ROOT / "bench" / "families" / "test"


def entropy(items):
    """Shannon entropy of a list of categorical values."""
    if not items: return 0.0
    c = Counter(items)
    n = len(items)
    return -sum((v/n) * math.log2(v/n) for v in c.values() if v > 0)


def run_one(bench: Path, tag: str, delay_ms: int = 1500) -> dict | None:
    db = f"/tmp/agi_dist_{tag}.sqlite3"
    ws = f"/tmp/agi_dist_{tag}_ws"
    for p in (db,):
        with contextlib.suppress(FileNotFoundError): os.remove(p)
    shutil.rmtree(ws, ignore_errors=True)

    env = {**os.environ, "AGI_STORAGE_PATH": db, "AGI_FS_ROOT": ws, "PYTHONPATH": "src"}
    args = [sys.executable, "-m", "agi", "eval", "run",
            "--bench", str(bench), "--seed", "all",
            "--strategy", "greedy", "--delay-ms", str(delay_ms)]
    try:
        p = subprocess.run(args, cwd=ROOT, env=env,
                           capture_output=True, text=True, timeout=2400)
        return json.loads(p.stdout)
    except Exception as e:
        print(f"  [!] {tag}: {type(e).__name__}: {e}", file=sys.stderr)
        return None
    finally:
        with contextlib.suppress(FileNotFoundError): os.remove(db)
        shutil.rmtree(ws, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--out", required=True)
    ap.add_argument("--delay-ms", type=int, default=1500)
    ap.add_argument("--families", default="", help="comma-sep names; empty = all")
    args = ap.parse_args()

    os.chdir(ROOT)
    wanted = set(args.families.split(",")) if args.families else None
    family_files = sorted(FAMILY_DIR.glob("fam*.jsonl"))

    all_obs = []       # list of (family, item_id, passed)
    per_family = defaultdict(list)

    for fam in family_files:
        name = fam.stem
        if wanted and name not in wanted:
            continue
        print(f"\n  {name} ...")
        for r in range(args.runs):
            tag = f"{name}_r{r}"
            d = run_one(fam, tag, args.delay_ms)
            if d is None:
                print(f"    run {r+1}: FAILED"); continue
            print(f"    run {r+1}: {d['passed']}/{d['total']} = {d['accuracy']:.2f}")
            for it in d.get("items", []):
                passed = bool(it.get("passed"))
                all_obs.append((name, it.get("id", "?"), passed))
                per_family[name].append(passed)

    if not all_obs:
        print("\nno observations — aborting"); return

    # --- entropy ---
    labels = ["pass" if p else "fail" for _, _, p in all_obs]
    H_total = entropy(labels)

    weighted = []
    for fam, ps in per_family.items():
        if not ps: continue
        weighted.append((len(ps), entropy(["pass" if p else "fail" for p in ps])))
    total_n = sum(w for w, _ in weighted) or 1
    H_conditional = sum((w / total_n) * h for w, h in weighted)

    MI = H_total - H_conditional

    # --- report ---
    print("\n=== RESULTS ===")
    print(f"  observations:        {len(all_obs)}")
    print(f"  H(pass):             {H_total:.3f} bits")
    print(f"  H(pass|family):      {H_conditional:.3f} bits")
    print(f"  I(family; pass):     {MI:.3f} bits")
    if MI < 0.1:
        verdict = "scattered — possible general mechanism"
    elif MI < 0.3:
        verdict = "moderately clustered — mixed"
    else:
        verdict = "strongly clustered — narrow agent"
    print(f"  verdict:             {verdict}")

    print("\n  per-family accuracy:")
    for fam in sorted(per_family):
        ps = per_family[fam]
        print(f"    {fam:8s}  {sum(ps)}/{len(ps)} = {sum(ps)/len(ps):.2f}")

    out = Path(args.out)
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({
        "families": sorted(per_family),
        "runs_per_family": args.runs,
        "n_observations": len(all_obs),
        "entropy_total": H_total,
        "entropy_conditional": H_conditional,
        "mutual_information": MI,
        "verdict": verdict,
        "per_family": {
            fam: {
                "n": len(ps),
                "passes": sum(ps),
                "accuracy": sum(ps)/len(ps) if ps else 0,
            } for fam, ps in per_family.items()
        },
    }, indent=2))
    print(f"\n  wrote {out}")


if __name__ == "__main__":
    main()
