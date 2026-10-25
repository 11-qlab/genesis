#!/usr/bin/env python3
"""Compare each item's answer.txt against seed.txt to derive the TRUE label."""
import json, pathlib, sys

TRAJ = pathlib.Path("artifacts/runs/v2-manual/trajectories.jsonl")
WS   = pathlib.Path("artifacts/runs/20261024-200026")
OUT  = pathlib.Path("artifacts/esf/ground_truth.json")

def classify(seed_text, ans_text):
    if ans_text is None:
        return "MISSING"
    if seed_text.strip() and seed_text.strip() in ans_text:
        return "CORRECT"
    # unresolved template detection
    for marker in ("{{", "${", "$read_", "<content>", "<count>", "{{content}}"):
        if marker in ans_text:
            return "UNRESOLVED_TEMPLATE"
    return "WRONG_CONTENT"

rows = []
for line in TRAJ.read_text().strip().splitlines():
    t = json.loads(line)
    fam, num = t["item_id"].rsplit("-", 1)
    ws = WS / f"_ws_{fam}_{int(num)}"
    seed_p = ws / "seed.txt"
    ans_p  = ws / "answer.txt"
    seed = seed_p.read_text() if seed_p.exists() else ""
    ans  = ans_p.read_text()  if ans_p.exists() else None
    true_label = classify(seed, ans)
    rows.append({
        "item": t["item_id"], "family": fam,
        "seed": seed.strip()[:40],
        "answer": (ans or "<missing>").strip()[:40],
        "true_label": true_label,
    })

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(rows, indent=2))

from collections import Counter
print(f"wrote {OUT}  ({len(rows)} items)")
print("\ntrue-label distribution:")
for k, v in Counter(r["true_label"] for r in rows).most_common():
    print(f"  {k:<22} {v}")
print("\nper family:")
for fam in sorted({r["family"] for r in rows}):
    sub = [r for r in rows if r["family"] == fam]
    print(f"  {fam}: {dict(Counter(r['true_label'] for r in sub))}")
