#!/usr/bin/env bash
# Run compositional.jsonl against the configured provider and split
# accuracy by `novel_ordering` tag (0 = baseline, 1 = novel composition).
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -z "${AGI_API_KEY:-}" ]; then
    echo "AGI_API_KEY required"
    exit 2
fi

export AGI_PROVIDER_KIND=openai_compat
export AGI_PROVIDER="${AGI_PROVIDER:-groq}"
export AGI_BASE_URL="${AGI_BASE_URL:-https://api.groq.com/openai/v1}"
export AGI_MODEL="${AGI_MODEL:-openai/gpt-oss-120b}"
export PYTHONPATH=src

DELAY="${DELAY_MS:-20000}"

STORE="/tmp/agi_comp.sqlite3"
WS="/tmp/agi_comp_ws"
rm -f "$STORE"; mkdir -p "$WS"
export AGI_STORAGE_PATH="$STORE"
export AGI_FS_ROOT="$WS"

echo "=== compositional.jsonl (20 items, ${DELAY}ms pacing) ==="
python3 -m agi eval run --bench bench/compositional.jsonl \
    --seed all --delay-ms "$DELAY" --markdown | tee /tmp/comp.md | tail -40

echo ""
echo "=== baseline vs novel split ==="
python3 - <<'PY'
import json, re, pathlib

# Parse the report JSON side-file if present, else reconstruct
md = pathlib.Path("/tmp/comp.md").read_text()

# The report has a per-item table; extract novelty from the bench file
bench = {}
for line in pathlib.Path("bench/compositional.jsonl").read_text().splitlines():
    if not line.strip():
        continue
    item = json.loads(line)
    bench[item["id"]] = item.get("novel_ordering", 0)

# Parse per-item rows
rows = re.findall(r"\|\s*(comp-\d+)\s*\|\s*(\w+)\s*\|\s*(yes|no)\s*\|", md)
base_pass, base_total = 0, 0
novel_pass, novel_total = 0, 0
for item_id, status, passed in rows:
    is_novel = bench.get(item_id, 0)
    if is_novel:
        novel_total += 1
        novel_pass += 1 if passed == "yes" else 0
    else:
        base_total += 1
        base_pass += 1 if passed == "yes" else 0

print(f"  baseline (novel=0): {base_pass}/{base_total}")
print(f"  novel    (novel=1): {novel_pass}/{novel_total}")
if base_total and novel_total:
    bp = base_pass / base_total
    np_ = novel_pass / novel_total
    print(f"  baseline acc = {bp:.4f}")
    print(f"  novel    acc = {np_:.4f}")
    print(f"  delta        = {np_ - bp:+.4f}")
PY
