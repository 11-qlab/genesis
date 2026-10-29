#!/usr/bin/env python3
"""McNemar exact test on paired (baseline vs executor_patch) outcomes, with BH."""
from __future__ import annotations
import json, math, sys
from collections import defaultdict
from pathlib import Path

def exact_binom_two_sided(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n)
    return min(1.0, 2 * tail)

def bh(pvals: list[float]) -> list[float]:
    m = len(pvals)
    order = sorted(range(m), key=lambda i: pvals[i])
    adj = [0.0] * m
    prev = 1.0
    for rank in range(m - 1, -1, -1):
        i = order[rank]
        val = min(prev, pvals[i] * m / (rank + 1))
        adj[i] = val
        prev = val
    return adj

def main(path: str) -> int:
    rows = [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]
    # pair by (family, task_id)
    by_cond = defaultdict(dict)
    for r in rows:
        by_cond[r["condition"]][(r["family"], r["task_id"])] = r["success"]

    pairs = sorted(set(by_cond["baseline"]) & set(by_cond["executor_patch"]))
    if not pairs:
        print("no paired baseline/executor_patch records", file=sys.stderr)
        return 2

    fam_counts = defaultdict(lambda: {"b": 0, "c": 0, "n": 0})
    for key in pairs:
        b_ok = by_cond["baseline"][key]
        e_ok = by_cond["executor_patch"][key]
        fam = key[0]
        fam_counts[fam]["n"] += 1
        if (not b_ok) and e_ok: fam_counts[fam]["b"] += 1  # fix
        if b_ok and (not e_ok): fam_counts[fam]["c"] += 1  # regression

    fams = sorted(fam_counts)
    raw = [exact_binom_two_sided(fam_counts[f]["b"], fam_counts[f]["c"]) for f in fams]
    adj = bh(raw)

    print(f"{'family':>6} {'n':>3} {'b(fix)':>7} {'c(reg)':>7} {'p_raw':>8} {'p_bh':>8}")
    for f, p, pa in zip(fams, raw, adj):
        print(f"{f:>6} {fam_counts[f]['n']:>3} {fam_counts[f]['b']:>7} "
              f"{fam_counts[f]['c']:>7} {p:>8.4f} {pa:>8.4f}")
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "results/runs.jsonl"))
