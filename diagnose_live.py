#!/usr/bin/env python3
import json
from collections import Counter
from pathlib import Path

rows = [json.loads(l) for l in Path("results/runs.jsonl").read_text().splitlines() if l.strip()]
live = [r for r in rows if r["mode"] == "live"]
print(f"live rows: {len(live)}\n")
print("--- error histogram ---")
for err, n in Counter(r.get("error", "<none>") for r in live).most_common():
    print(f"{n:4d}x  {err}\n")
print("--- one example per condition ---")
seen = set()
for r in live:
    k = (r["family"], r["condition"])
    if k in seen: continue
    seen.add(k)
    print(json.dumps(r, indent=2))
