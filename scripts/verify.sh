#!/usr/bin/env bash
# Full verification gate. Runs entirely offline by design: it strips
# every AGI_* env var first, so a shell with real provider exports
# cannot accidentally point this gate at a network endpoint.
#
# To explicitly test against a live provider, use scripts/measure_with_keys.sh
# or `agi eval run` directly — not this script.
set -euo pipefail
cd "$(dirname "$0")/.."

# Hermetic: strip AGI_* so verify never depends on the caller's shell.
for _name in $(env | awk -F= '/^AGI_/ {print $1}'); do
    unset "$_name" 2>/dev/null || true
done
unset AGI_API_KEYS AGI_API_KEY AGI_CONFIG 2>/dev/null || true

# Pin to defaults so provider kind is 'echo', fs root is repo state,
# storage is ephemeral under /tmp/verify.
export AGI_PROVIDER_KIND=echo
export AGI_PROVIDER=echo
export AGI_MODEL=echo-1
export AGI_STORAGE_PATH=/tmp/agi_verify.sqlite3
export AGI_FS_ROOT=/tmp/agi_verify_ws
export PYTHONPATH=src
mkdir -p "$AGI_FS_ROOT"
rm -f "$AGI_STORAGE_PATH"

echo "[verify] pytest"
python3 -m pytest -q --no-header

echo "[verify] ruff"
ruff check src tests

echo "[verify] doctor"
python3 -m agi doctor >/dev/null

echo "[verify] run end-to-end"
python3 -m agi run "list the workspace" >/dev/null

echo "[verify] eval run"
TMP_EVAL=$(mktemp -d)
mkdir -p "$TMP_EVAL/ws"
AGI_STORAGE_PATH="$TMP_EVAL/agi.sqlite3" AGI_FS_ROOT="$TMP_EVAL/ws" \
    python3 -m agi eval run --bench bench/workspace_list.jsonl \
    > "$TMP_EVAL/out.json"
python3 -c "import json; d=json.load(open('$TMP_EVAL/out.json')); assert d['accuracy']==1.0, d"
rm -rf "$TMP_EVAL"

echo "[verify] api /health"
TMP=$(mktemp -d)
PORT=$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1]); s.close()')
AGI_STORAGE_PATH="$TMP/agi.sqlite3" AGI_FS_ROOT="$TMP/ws" \
    python3 -m agi serve --port "$PORT" > "$TMP/serve.log" 2>&1 &
SPID=$!
trap 'kill $SPID 2>/dev/null || true; wait $SPID 2>/dev/null || true; rm -rf "$TMP"' EXIT
ready=0
for _ in $(seq 1 100); do
    if curl -sf "http://127.0.0.1:$PORT/health" > "$TMP/health.json" 2>/dev/null; then
        ready=1; break
    fi
    sleep 0.1
done
if [ "$ready" != "1" ]; then
    echo "[verify] API did not come up"; cat "$TMP/serve.log"; exit 1
fi
python3 -c "import json; d=json.load(open('$TMP/health.json')); assert d['ok'] is True"
kill "$SPID" 2>/dev/null || true
wait "$SPID" 2>/dev/null || true
trap - EXIT
rm -rf "$TMP"

echo "[verify] fresh-copy smoke"
TMP_FRESH=$(mktemp -d)
cp -r src config bench bin scripts tests pyproject.toml README.md LICENSE .gitignore "$TMP_FRESH/"
mkdir -p "$TMP_FRESH/state/workspace"
(
    cd "$TMP_FRESH"
    PYTHONPATH=src python3 -m agi doctor >/dev/null
    AGI_STORAGE_PATH="$TMP_FRESH/state/agi.sqlite3" \
    AGI_FS_ROOT="$TMP_FRESH/state/workspace" \
    PYTHONPATH=src python3 -m agi run "list workspace" >/dev/null
)
rm -rf "$TMP_FRESH"

echo "[verify] OK"
