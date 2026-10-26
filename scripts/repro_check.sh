#!/usr/bin/env bash
# Runs reproduce.sh into an isolated output dir so tracked artifacts/ stay clean.
set -euo pipefail
cd "$(dirname "$0")/.."

: "${AGI_BASE_URL:?AGI_BASE_URL not set}"
: "${AGI_MODEL:?AGI_MODEL not set}"
: "${AGI_API_KEY:=EMPTY}"

OUT="${ARTIFACTS_DIR:-/tmp/repro_check}"
mkdir -p "$OUT"

# Patch-on-the-fly: run reproduce.sh with its artifacts/ hardcodes redirected
# only if it respects ARTIFACTS_DIR; otherwise warn and run in place.
if grep -q 'ARTIFACTS_DIR' reproduce.sh; then
  echo "[repro] reproduce.sh respects ARTIFACTS_DIR -> $OUT"
  ARTIFACTS_DIR="$OUT" ./reproduce.sh 2>&1 | tee "$OUT/reproduce.log"
else
  echo "[repro] WARN: reproduce.sh does not honor ARTIFACTS_DIR."
  echo "[repro] running in place — git status will dirty artifacts/traces/."
  ./reproduce.sh 2>&1 | tee "$OUT/reproduce.log"
fi

echo
echo "== verdict check (count-level, not label-level) =="
python3 - <<'PY'
import json, pathlib
exp = {"H001":"NOT_A_TEST","H002":"PASS","H003":"REJECTED","H004":"SCOPED","H005":"REJECTED"}
ok = True
for h, want in exp.items():
    p = pathlib.Path(f"results/{h}.json")
    if not p.exists(): print(f"{h}: MISSING"); ok=False; continue
    r = json.loads(p.read_text())
    got = r.get("verdict")
    mark = "ok " if got == want else "FAIL"
    print(f"{h}: {mark} verdict={got} (want {want})  keys={sorted(r.keys())[:6]}")
    if got != want: ok = False
print("PASS" if ok else "FAIL")
raise SystemExit(0 if ok else 1)
PY
