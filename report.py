#!/usr/bin/env python3
"""Markdown summary of results/runs.jsonl."""
from __future__ import annotations
import json, sys
from collections import defaultdict
from pathlib import Path

def main(path: str) -> int:
    rows = [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]
    if not rows:
        print("no records", file=sys.stderr); return 2
    agg = defaultdict(lambda: {"n": 0, "ok": 0, "placeholder": 0, "errors": 0})
    for r in rows:
        k = (r["mode"], r["family"], r["condition"])
        a = agg[k]
        a["n"] += 1
        a["ok"] += int(r["success"])
        a["placeholder"] += int(r["placeholder_written"])
        a["errors"] += int(bool(r.get("error")))

    print("# Cross-tool substitution — results\n")
    print("| mode | family | condition | n | success | placeholders | errors | rate |")
    print("|---|---|---|---|---|---|---|---|")
    for (mode, fam, cond), a in sorted(agg.items()):
        rate = a["ok"] / a["n"] if a["n"] else 0.0
        print(f"| {mode} | {fam} | {cond} | {a['n']} | {a['ok']} | "
              f"{a['placeholder']} | {a['errors']} | {rate:.2%} |")
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "results/runs.jsonl"))
