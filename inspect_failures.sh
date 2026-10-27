#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")"

python3 - <<'PY'
import json, glob
from pathlib import Path

records = [json.loads(l) for l in open("signals_adv/runs.jsonl") if l.strip()]
failed = [r for r in records if not r["passed"]]

print(f"Total failed trials: {len(failed)} of {len(records)}\n")

for r in failed:
    print("=" * 78)
    print(f"MODEL  : {r['model']}")
    print(f"TASK   : {r['task']}")
    print(f"TRIAL  : {r.get('trial')}")
    print(f"REASON : {r['reason']}")
    print(f"BUGS   : {r.get('bugs') or 'none matched'}")
    print("-" * 78)
    print("CODE:")
    print(r.get("code", "<not captured>"))
    print("-" * 78)
    print("STDERR (tail):")
    print((r.get("stderr") or "")[-800:])
    print()

# Group by (task, model) to expose per-cell patterns
print("=" * 78)
print("FAILURE CLUSTERS (grouped by mechanism)")
print("=" * 78)
from collections import defaultdict, Counter
clusters = defaultdict(list)
for r in failed:
    key = tuple(sorted(r.get("bugs") or [r["reason"]]))
    clusters[key].append(f"{r['model']}/{r['task']}/t{r.get('trial')}")

for k, runs in clusters.items():
    print(f"\n  mechanism: {' + '.join(k)}")
    for run in runs:
        print(f"    - {run}")
PY
