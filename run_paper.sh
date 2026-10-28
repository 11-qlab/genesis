#!/usr/bin/env bash
# run_paper.sh — end-to-end. Ground truth first, paper numbers last.
set -euo pipefail
cd "$(dirname "$0")"

RED=$(tput setaf 1 2>/dev/null || true); GRN=$(tput setaf 2 2>/dev/null || true)
YEL=$(tput setaf 3 2>/dev/null || true); RST=$(tput sgr0 2>/dev/null || true)
step(){ echo; echo "${GRN}━━━ $* ━━━${RST}"; }

if [[ "${GROQ_API_KEY:-}" == gsk_uBju* ]]; then
  echo "${RED}[BLOCK] GROQ_API_KEY is the exposed key. Rotate before proceeding.${RST}"
  echo "        console.groq.com/keys → revoke → create → export GROQ_API_KEY=…"
  exit 1
fi

step "1/4  extract anchors from TEMPLATES + _known_correct_for"
./10_extract_anchors.py

step "2/4  verify anchors (the ground-truth oracle)"
./14_heldout_split.py
./14_heldout_split.py
./20_verify_anchors.py
./13_classify_too_strict.py

step "3/4  anomaly report (unexplained failures)"
./30_anomaly_report.py

step "4/4  paper numbers"
./40_paper_numbers.py || true
./41_fix_grounding_label.py | tee -a paper/numbers.md
./42_claims.py
./44_claim_both_splits.py
./44_claim_both_splits.py

echo
echo "${GRN}[ DONE ]${RST}"
echo "  bench/anchors/v1.jsonl        frozen anchor spec  (sha256 in v1.sha256)"
echo "  state/anchor_verdicts.jsonl   per-anchor execution verdicts"
echo "  state/anomalies.jsonl         failures the taxonomy cannot explain"
echo "  paper/numbers.md              paste-ready tables"
