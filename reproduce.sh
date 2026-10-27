#!/usr/bin/env bash
set -euo pipefail
OUT="${ARTIFACTS_DIR:-artifacts/traces}"
export ARTIFACTS_DIR="$OUT"
mkdir -p "$OUT"
# Refuse to run if artifacts/traces has uncommitted changes
if [ "$OUT" = "artifacts/traces" ]; then
  if ! git diff --quiet artifacts/traces/ 2>/dev/null; then
    echo "[reproduce] ERROR: artifacts/traces/ has uncommitted changes." >&2
    echo "[reproduce] Set ARTIFACTS_DIR=/tmp/repro to run isolated." >&2
    exit 1
  fi
  echo "[reproduce] WARN: writing to committed artifacts/traces/ — set ARTIFACTS_DIR to avoid clobbering paper evidence" >&2
fi


set -euo pipefail
: "${AGI_BASE_URL:?set AGI_BASE_URL to an OpenAI-compatible endpoint serving gpt-oss-20b}"
export PYTHONPATH=src
export AGI_MODEL="${AGI_MODEL:-gpt-oss-20b}"

mkdir -p artifacts/traces docs/research

echo "== split bench =="
head -5  bench/families/seed/fam14in.jsonl > /tmp/trace_seed.jsonl
head -10 bench/families/test/fam14in.jsonl > /tmp/trace_test.jsonl

echo "== trace capture: seed (5x2) + test (10x2) = 30 calls =="
python3 scripts/trace_planner.py --bench /tmp/trace_seed.jsonl --n 5 \
  --out $OUT/trace_seed.jsonl
python3 scripts/trace_planner.py --bench /tmp/trace_test.jsonl --n 10 \
  --out $OUT/trace_test.jsonl

echo "== analysis =="
python3 scripts/analyze_traces_v2.py

echo
echo "done. See docs/research/TRACE_RESULTS.md and WORKSHOP_PAPER.md 4.2/5"