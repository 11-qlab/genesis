#!/usr/bin/env bash
# Paced hard-benchmark measurement against the configured provider.
#
# Usage (Groq example):
#   export AGI_API_KEY=gsk_...
#   ./scripts/measure.sh
#
# Required env: AGI_API_KEY, AGI_PROVIDER_KIND=openai_compat, AGI_PROVIDER,
#               AGI_BASE_URL, AGI_MODEL.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ "${AGI_PROVIDER_KIND:-}" != "openai_compat" ]; then
    echo "AGI_PROVIDER_KIND must be openai_compat (got: ${AGI_PROVIDER_KIND:-unset})"
    exit 2
fi

export PYTHONPATH=src
export AGI_STORAGE_PATH="${AGI_STORAGE_PATH:-/tmp/agi_measure.sqlite3}"
export AGI_FS_ROOT="${AGI_FS_ROOT:-/tmp/agi_measure_ws}"
mkdir -p "$AGI_FS_ROOT"
rm -f "$AGI_STORAGE_PATH"

DELAY="${DELAY_MS:-5000}"

echo "=== workspace_list (baseline, 3 items) ==="
python3 -m agi eval run --bench bench/workspace_list.jsonl --delay-ms 0 --markdown | tee /tmp/m_ws_base.md | tail -12

echo ""
echo "=== workspace_list_hard (20 paraphrased, ${DELAY}ms pacing) ==="
python3 -m agi eval run --bench bench/workspace_list_hard.jsonl --delay-ms "$DELAY" --markdown | tee /tmp/m_ws_hard.md | tail -40

echo ""
echo "=== memory_search (baseline, 3 items, seeded) ==="
python3 -m agi eval run --bench bench/memory_search.jsonl --seed memory --delay-ms 0 --markdown | tee /tmp/m_ms_base.md | tail -12

echo ""
echo "=== memory_search_hard (15 paraphrased, seeded, ${DELAY}ms pacing) ==="
python3 -m agi eval run --bench bench/memory_search_hard.jsonl --seed memory --delay-ms "$DELAY" --markdown | tee /tmp/m_ms_hard.md | tail -40

echo ""
echo "=== summary (accuracy per benchmark) ==="
for f in /tmp/m_ws_base.md /tmp/m_ws_hard.md /tmp/m_ms_base.md /tmp/m_ms_hard.md; do
    if [ -f "$f" ]; then
        name=$(basename "$f" .md)
        acc=$(grep -m1 '| accuracy |' "$f" | awk -F'|' '{print $3}' | tr -d ' ')
        n=$(grep -m1 '| total |' "$f" | awk -F'|' '{print $3}' | tr -d ' ')
        p=$(grep -m1 '| passed |' "$f" | awk -F'|' '{print $3}' | tr -d ' ')
        printf '  %-14s %s/%s = %s\n' "$name" "$p" "$n" "$acc"
    fi
done
