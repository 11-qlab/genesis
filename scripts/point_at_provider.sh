#!/usr/bin/env bash
# One-shot: probe a real provider, then run both benchmarks against it.
#
# Usage:
#   ./scripts/point_at_provider.sh <BASE_URL> <MODEL> [API_KEY_ENV_VAR]
set -euo pipefail
cd "$(dirname "$0")/.."

if [ "$#" -lt 2 ]; then
    echo "usage: $0 <BASE_URL> <MODEL> [API_KEY_ENV_VAR]"
    exit 2
fi

BASE_URL="$1"
MODEL="$2"
KEY_ENV="${3:-AGI_API_KEY}"

if [ -z "${!KEY_ENV:-}" ]; then
    echo "[point_at_provider] WARNING: \$$KEY_ENV is empty; most providers will 401"
fi

export AGI_PROVIDER_KIND=openai_compat
export AGI_PROVIDER=external
export AGI_BASE_URL="$BASE_URL"
export AGI_MODEL="$MODEL"
export AGI_API_KEY_ENV="$KEY_ENV"
export PYTHONPATH=src

TMP=$(mktemp -d)
mkdir -p "$TMP/ws"
trap 'rm -rf "$TMP"' EXIT
export AGI_STORAGE_PATH="$TMP/agi.sqlite3"
export AGI_FS_ROOT="$TMP/ws"

echo ""
echo "=== probe ($BASE_URL / $MODEL) ==="
python3 -m agi provider probe || PROBE_RC=$?

echo ""
echo "=== chat smoke ==="
python3 -m agi chat "reply with the single word: ok" || CHAT_RC=$?

echo ""
echo "=== eval: workspace_list (fs loop) ==="
python3 -m agi eval run --bench bench/workspace_list.jsonl --markdown || EVAL_WS_RC=$?

echo ""
echo "=== eval: memory_search (RAG loop, seeded) ==="
python3 -m agi eval run --bench bench/memory_search.jsonl --seed memory --markdown || EVAL_MEM_RC=$?

echo ""
echo "=== summary ==="
printf '  probe        exit=%s\n' "${PROBE_RC:-0}"
printf '  chat         exit=%s\n' "${CHAT_RC:-0}"
printf '  eval_ws      exit=%s\n' "${EVAL_WS_RC:-0}"
printf '  eval_mem     exit=%s\n' "${EVAL_MEM_RC:-0}"
echo ""
echo "NOTE: eval pass rates here measure the model + harness. Read the"
echo "      WHAT_THIS_IS_NOT.md section on accuracy before drawing any"
echo "      conclusion beyond 'the loop closed against a real model'."
