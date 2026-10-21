#!/usr/bin/env bash
# F3/F4 diagnostic — dump per-item calibration_estimate alongside outcome.
#
# Reads both the JSON (per-item values) AND the contaminated status.
# CASE 2 is only claimed after checking contaminated:false — otherwise
# the item's `est` is not a real measurement at all.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -z "${AGI_API_KEYS:-}" ] && [ -z "${AGI_API_KEY:-}" ]; then
    echo "AGI_API_KEYS or AGI_API_KEY required"
    exit 2
fi

export AGI_PROVIDER_KIND=openai_compat
export AGI_PROVIDER="${AGI_PROVIDER:-groq}"
export AGI_BASE_URL="${AGI_BASE_URL:-https://api.groq.com/openai/v1}"
export AGI_MODEL="${AGI_MODEL:-openai/gpt-oss-120b}"
export AGI_STORAGE_PATH="${AGI_STORAGE_PATH:-/tmp/agi_cal_dump.sqlite3}"
export AGI_FS_ROOT="${AGI_FS_ROOT:-/tmp/agi_cal_dump_ws}"
export PYTHONPATH=src
rm -f "$AGI_STORAGE_PATH"; mkdir -p "$AGI_FS_ROOT"

echo "=== error_recovery calibration run (20 items) ==="
python3 -m agi eval run --bench bench/error_recovery.jsonl \
    --strategy calibration --delay-ms "${DELAY_MS:-4000}" 2>/dev/null \
    > /tmp/agi_cal_dump.json

python3 - <<'PY_INNER'
import json
with open("/tmp/agi_cal_dump.json") as f:
    d = json.load(f)

acc = d["accuracy"]
brier = d.get("brier")
ece = d.get("ece")
contaminated = d.get("contaminated")
rate_limited = d.get("rate_limited_items")
strategy = d.get("strategy")

print(f"strategy:      {strategy}")
print(f"accuracy:      {acc:.4f}")
print(f"brier:         {brier}")
print(f"ece:           {ece}")
print(f"contaminated:  {contaminated}")
print(f"rate_limited:  {rate_limited} items")
print()

if contaminated:
    print("*** CONTAMINATED RUN — DISCARD. ***")
    print("    More than 10% of items hit rate limits.")
    print("    Increase DELAY_MS and re-run before drawing any conclusion.")
    print()

items = d.get("items") or []
print(f"{'item_id':12s} {'estimate':>8s} {'outcome':>8s}")
print("-" * 32)
all_none = True
values = []
for o in items:
    est = o.get("calibration_estimate")
    ok = "pass" if o.get("passed") else "fail"
    print(f"{o['id']:12s} {str(est):>8s} {ok:>8s}")
    if est is not None:
        all_none = False
        values.append(est)
print()

if contaminated:
    print("Verdict on per-item evidence: N/A (run contaminated)")
elif all_none:
    print("CASE A: all estimates are None (field missing). Re-run after fix.")
elif len(set(values)) == 1:
    print(f"CASE B: all estimates are {values[0]}. Model returns constant.")
else:
    print(f"CASE C: estimates vary across {len(set(values))} values: {sorted(set(values))}")
PY_INNER

rm -f /tmp/agi_cal_dump.json
