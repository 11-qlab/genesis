#!/usr/bin/env bash
# Usage:
#   ./run_all.sh simulate   # validates the pipeline, $0, expect ~0.70 baseline fails
#   ./run_all.sh live       # real model + real cfh tools (wire call_model first)
set -euo pipefail
MODE="${1:-simulate}"
OUT="results/runs.jsonl"

rm -rf results && mkdir -p results

FLAGS=()
if [[ "$MODE" == "simulate" ]]; then
  FLAGS+=(--simulate --repeats 20 --seed 7)
else
  FLAGS+=(--repeats 1 --seed 0)
fi

for fam in C D; do
  for cond in baseline prompt_patch executor_patch; do
    python3 run_family.py --family "$fam" --condition "$cond" --out "$OUT" "${FLAGS[@]}"
  done
done

echo; echo "=== report ==="
python3 report.py "$OUT" | tee results/report.md
echo; echo "=== McNemar (baseline vs executor_patch) ==="
python3 mcnemar.py "$OUT" | tee results/mcnemar.txt
