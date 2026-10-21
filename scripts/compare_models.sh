#!/usr/bin/env bash
# Run the two cold benchmarks against multiple models on one endpoint.
# Prints a comparison table; does not touch the platform code.
#
# Usage:
#   export AGI_API_KEY=gsk_...
#   ./scripts/compare_models.sh openai/gpt-oss-120b openai/gpt-oss-20b qwen/qwen3.8-27b
set -euo pipefail
cd "$(dirname "$0")/.."

if [ "$#" -lt 1 ]; then
    echo "usage: $0 <model> [<model> ...]"
    exit 2
fi
if [ -z "${AGI_API_KEY:-}" ]; then
    echo "AGI_API_KEY is required"
    exit 2
fi

export AGI_PROVIDER_KIND=openai_compat
export AGI_PROVIDER="${AGI_PROVIDER:-groq}"
export AGI_BASE_URL="${AGI_BASE_URL:-https://api.groq.com/openai/v1}"
export PYTHONPATH=src

DELAY="${DELAY_MS:-5000}"

TABLE=/tmp/model_comparison.md
: > "$TABLE"
echo "| model | benchmark | accuracy | passed/total |" >> "$TABLE"
echo "| --- | --- | --- | --- |" >> "$TABLE"

_run_one() {
    local model="$1" bench="$2" seed="$3" delay="$4"
    local store ws extra
    store="/tmp/agi_cmp_$(echo "$model-$bench" | tr '/:' '__').sqlite3"
    ws="/tmp/agi_cmp_$(echo "$model-$bench" | tr '/:' '__')_ws"
    rm -f "$store"; mkdir -p "$ws"
    export AGI_MODEL="$model"
    export AGI_STORAGE_PATH="$store"
    export AGI_FS_ROOT="$ws"
    extra=""
    if [ -n "$seed" ]; then
        extra="--seed $seed"
    fi
    local out
    out=$(python3 -m agi eval run --bench "$bench" $extra --delay-ms "$delay" --markdown 2>/dev/null || true)
    local acc pass total
    acc=$(echo "$out" | grep -m1 '| accuracy |' | awk -F'|' '{print $3}' | tr -d ' ')
    pass=$(echo "$out" | grep -m1 '| passed |' | awk -F'|' '{print $3}' | tr -d ' ')
    total=$(echo "$out" | grep -m1 '| total |' | awk -F'|' '{print $3}' | tr -d ' ')
    rm -f "$store"; rm -rf "$ws"
    echo "| $model | $(basename "$bench") | ${acc:-error} | ${pass:-?}/${total:-?} |" >> "$TABLE"
    echo "  $model / $(basename "$bench"): ${pass:-?}/${total:-?} = ${acc:-error}"
}

for MODEL in "$@"; do
    echo ""
    echo "=== $MODEL ==="
    _run_one "$MODEL" bench/task_chain.jsonl all "$DELAY"
    _run_one "$MODEL" bench/error_recovery.jsonl "" "$DELAY"
done

echo ""
echo "=== comparison table ==="
cat "$TABLE"
