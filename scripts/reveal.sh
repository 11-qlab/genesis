#!/usr/bin/env bash
# Run both bundled benchmarks, then print the honest interpretation of
# what those accuracy numbers actually measure. Read-only otherwise.
set -euo pipefail
cd "$(dirname "$0")/.."

TMP=$(mktemp -d)
mkdir -p "$TMP/ws"
trap 'rm -rf "$TMP"' EXIT

echo "=== running workspace_list.jsonl (fs loop) ==="
AGI_STORAGE_PATH="$TMP/e.sqlite3" AGI_FS_ROOT="$TMP/ws" \
    PYTHONPATH=src python3 -m agi eval run --bench bench/workspace_list.jsonl > /dev/null
WS_ID=$(AGI_STORAGE_PATH="$TMP/e.sqlite3" AGI_FS_ROOT="$TMP/ws" \
    PYTHONPATH=src python3 -m agi eval list 2>/dev/null | grep -oP '^\│ \K[0-9]+' | head -1)

echo "=== running memory_search.jsonl (RAG loop, seeded) ==="
AGI_STORAGE_PATH="$TMP/e.sqlite3" AGI_FS_ROOT="$TMP/ws" \
    PYTHONPATH=src python3 -m agi eval run --bench bench/memory_search.jsonl --seed memory > /dev/null
MEM_ID=$(AGI_STORAGE_PATH="$TMP/e.sqlite3" AGI_FS_ROOT="$TMP/ws" \
    PYTHONPATH=src python3 -m agi eval list 2>/dev/null | grep -oP '^\│ \K[0-9]+' | head -1)

echo ""
echo "=== explain workspace_list run $WS_ID ==="
AGI_STORAGE_PATH="$TMP/e.sqlite3" AGI_FS_ROOT="$TMP/ws" \
    PYTHONPATH=src python3 -m agi eval explain "$WS_ID"

echo ""
echo "=== explain memory_search run $MEM_ID ==="
AGI_STORAGE_PATH="$TMP/e.sqlite3" AGI_FS_ROOT="$TMP/ws" \
    PYTHONPATH=src python3 -m agi eval explain "$MEM_ID"

echo ""
echo "=== the trick, in one sentence ==="
echo "Echo is a regex fixture, not a model. 1.0 on echo measures the harness,"
echo "not intelligence. To measure reasoning, point AGI_PROVIDER_KIND at a"
echo "real endpoint and rerun. See docs/development/WHAT_THIS_IS_NOT.md."
