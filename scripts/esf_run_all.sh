#!/usr/bin/env bash
set -euo pipefail

TRAJ_DIR="${TRAJ_DIR:-artifacts/trajectories}"
RENDER_DIR="${RENDER_DIR:-artifacts/esf/rendered}"
OUT_DIR="${OUT_DIR:-artifacts/esf}"

export AGI_BASE_URL="${AGI_BASE_URL:-http://localhost:8000/v1}"
export AGI_MODEL="${AGI_MODEL:-openai/gpt-oss-20b}"
export AGI_API_KEY="${AGI_API_KEY:-EMPTY}"

mkdir -p "$RENDER_DIR" "$OUT_DIR"

echo "== Step 1: render L1-L4 evidence ladders =="
for f in "$TRAJ_DIR"/*.json; do
  python scripts/esf_render_ladder.py "$f" "$RENDER_DIR"
done

echo "== Step 2: run absolute verification on gpt-oss-20b =="
python scripts/esf_run_absolute.py \
  --rendered-dir "$RENDER_DIR" \
  --out "$OUT_DIR/verdicts_absolute_20b.json" \
  --goal "Verify the tool-use trajectory above."

echo "== Step 3: aggregate curve =="
python scripts/esf_aggregate.py \
  --verdicts "$OUT_DIR/verdicts_absolute_20b.json" \
  --traj-dir "$TRAJ_DIR" \
  --out "$OUT_DIR/esf_curve_20b.json"

echo "done. curve -> $OUT_DIR/esf_curve_20b.json"
