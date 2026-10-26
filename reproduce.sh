#!/usr/bin/env bash
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
  --out artifacts/traces/trace_seed.jsonl
python3 scripts/trace_planner.py --bench /tmp/trace_test.jsonl --n 10 \
  --out artifacts/traces/trace_test.jsonl

echo "== analysis =="
python3 scripts/analyze_traces_v2.py

echo
echo "done. See docs/research/TRACE_RESULTS.md and WORKSHOP_PAPER.md 4.2/5"
