#!/usr/bin/env python3
"""Bench-split analysis: seed (value in goal) vs test (value from tool)."""
import json, re, sys
from collections import defaultdict, Counter
from math import comb
from pathlib import Path

def fisher(a, an, b, bn):
    n, k = an + bn, a + b
    p = lambda x: comb(an, x) * comb(bn, k - x) / comb(n, k)
    obs = p(a)
    return sum(p(x) for x in range(max(0, k - bn), min(an, k) + 1) if p(x) <= obs)

def load(path):
    if not Path(path).exists(): return []
    return [json.loads(l) for l in Path(path).read_text().strip().splitlines()]

datasets = {
    "seed (value in goal)":   load("artifacts/traces/trace_seed.jsonl"),
    "test (value from tool)": load("artifacts/traces/trace_test.jsonl"),
    "combined":                load("artifacts/traces/planner_traces.jsonl"),
}

print(f"{'dataset':<24}{'cond':<10}{'n':<4}{'placeholder':<13}{'literal':<9}{'other':<7}")
summary = {}
for name, rows in datasets.items():
    if not rows: 
        print(f"{name:<24}(missing)"); continue
    summary[name] = {}
    for cond in ("baseline", "patched"):
        sub = [r for r in rows if r["cond"] == cond]
        ph  = sum(1 for r in sub if r["class"] == "placeholder")
        lit = sum(1 for r in sub if r["class"] == "literal")
        summary[name][cond] = (ph, len(sub), lit)
        print(f"{name:<24}{cond:<10}{len(sub):<4}{ph:<13}{lit:<9}{len(sub)-ph-lit:<7}")

print("\n=== Fisher: baseline vs patched per dataset ===")
for name, d in summary.items():
    if "baseline" in d and "patched" in d:
        ph_b, n_b, _ = d["baseline"]
        ph_p, n_p, _ = d["patched"]
        p = fisher(ph_b, n_b, ph_p, n_p)
        sig = "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.10 else "ns"
        print(f"  {name:<24} {ph_b}/{n_b} vs {ph_p}/{n_p}  p = {p:.4f}  {sig}")

print("\n=== placeholder syntax, patched condition ===")
for name, rows in datasets.items():
    sub = [r for r in rows if r["cond"] == "patched" and r["class"] == "placeholder"]
    if not sub: continue
    syntaxes = Counter()
    for r in sub:
        c = r["content"] or ""
        if "{{" in c:        syntaxes["{{...}}"] += 1
        elif "${" in c:      syntaxes["${...}"] += 1
        elif "<" in c:       syntaxes["<content_from_sN>"] += 1
        else:                syntaxes["other"] += 1
    print(f"  {name:<24} {dict(syntaxes)}")
