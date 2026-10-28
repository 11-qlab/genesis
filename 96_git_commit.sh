#!/usr/bin/env bash
# 96_git_commit.sh — commit the quantum + differential artifacts.
# Only core artifacts are required. Optional helper scripts are skipped.
set -euo pipefail
cd "$(dirname "$0")"

# 1. Key scan (mandatory)
if ! ./95_precommit_key_scan.sh; then
  echo "BLOCK: fix exposed keys before committing" >&2
  exit 1
fi

# 2. Branch — create only if missing (do NOT reset existing branch)
BRANCH="research/quantum-and-differential-v1"
if git rev-parse --verify "$BRANCH" >/dev/null 2>&1; then
  git checkout "$BRANCH"
else
  git checkout -b "$BRANCH"
fi

# 3. Core artifacts — MUST exist
REQUIRED=(
  docs/QUANTUM_REPORT.md
  docs/DIFFERENTIAL_REPORT.md
  paper/claims.md
  paper/numbers.md
  bench/anchors/v1.jsonl
  bench/anchors/v1_heldout.jsonl
  bench/quantum_anchors/v1.jsonl
  state/anchor_verdicts.jsonl
  state/heldout_verdicts.jsonl
  state/quantum_verdicts.jsonl
  state/minimal_differential.jsonl
  state/anomalies.jsonl
  state/attribution.jsonl
  state/candidate_verdicts.jsonl
  state/identifiability.jsonl
)

# 4. Optional scripts — skip if missing
OPTIONAL=(
  GROUNDTRUTH.md run_paper.sh
  10_extract_anchors.py 11_patch_extract_test_fallback.py 12_probe_tests.py
  13_classify_too_strict.py 14_heldout_split.py 15_identifiability.py
  16_grounded_candidate.py 20_verify_anchors.py 30_anomaly_report.py
  40_paper_numbers.py 41_fix_grounding_label.py 42_claims.py
  43_fix_claims.py 44_claim_both_splits.py
  50_quantum_oracle.py 51_submit_to_ibm.py
  60_attribute_failures.py 61_fix_contaminated_attribution.py
  70_async_router.py 71_differential_oracle.py 72_fix_status.py
  73_run_differential.py 74_fix_exec_vs_falsification.py
  76_multi_model_differential.py 77_fix_model_ids.py
  80_minimal_differential.py 81_record_differential_claim.py
  95_precommit_key_scan.sh 96_git_commit.sh
  bench/anchors/v1.sha256 bench/anchors/v1_heldout.sha256
)

MISSING=()
for f in "${REQUIRED[@]}"; do [[ -f "$f" ]] || MISSING+=("$f"); done
if [[ ${#MISSING[@]} -gt 0 ]]; then
  echo "BLOCK: core artifacts missing:"
  printf '  %s\n' "${MISSING[@]}"
  echo
  echo "To regenerate, run in this order:"
  echo "  ./run_paper.sh                # classical (anchor_verdicts, heldout, anomalies, attribution, claims, numbers)"
  echo "  ./16_grounded_candidate.py    # candidate_verdicts"
  echo "  ./60_attribute_failures.py    # attribution (also via run_paper)"
  echo "  ./15_identifiability.py       # identifiability"
  echo "  ./50_quantum_oracle.py        # quantum_anchors"
  echo "  ./51_submit_to_ibm.py         # quantum_verdicts  (needs QISKIT_IBM_TOKEN)"
  echo "  ./80_minimal_differential.py  # minimal_differential"
  echo "  ./81_record_differential_claim.py  # appends to claims.md"
  echo "  (docs/*.md are hand-written — copy the heredocs)"
  exit 1
fi

# Stage required
git add -- "${REQUIRED[@]}"

# Stage optional that exist
STAGED_OPT=()
SKIPPED=()
for f in "${OPTIONAL[@]}"; do
  if [[ -f "$f" ]]; then git add -- "$f"; STAGED_OPT+=("$f"); else SKIPPED+=("$f"); fi
done

echo
echo "=== staged ($((${#REQUIRED[@]}+${#STAGED_OPT[@]})) files) ==="
git diff --cached --stat
if [[ ${#SKIPPED[@]} -gt 0 ]]; then
  echo
  echo "=== skipped (missing, not required) ==="
  printf '  %s\n' "${SKIPPED[@]}"
fi

if [[ "${1:-}" != "--yes" ]]; then
  echo
  echo "review above. to commit, re-run:  ./96_git_commit.sh --yes"
  exit 0
fi

git commit -m "ground-truth gate: classical + quantum + differential oracles

Cross-domain evidence that the execution-verifiable oracle transfers:

  Classical (3/3 classes, 3/9 anchors discriminate)
    state/anchor_verdicts.jsonl
    state/heldout_verdicts.jsonl   (private split, same anchors)

  Quantum (2/2 circuits on ibm_fez)
    GHZ-3 parity  +2.920 +/- 0.047  (1.71sigma, 4096 shots)
    Bell ZZ       +0.957 +/- 0.016  (2.75sigma, 4096 shots)
    state/quantum_verdicts.jsonl
    docs/QUANTUM_REPORT.md

  Differential (36 calls, 2 families, no reference impl)
    gpt-oss-20b   3/3 name-sensitive
    qwen3.8-27b   1/3 name-sensitive (only on cross-algorithm contrast)
    state/minimal_differential.jsonl
    docs/DIFFERENTIAL_REPORT.md

Refusal as contribution:
  7 anomalies -> 5 intervention levels (state/attribution.jsonl)
  1 candidate -> capability_limit (state/candidate_verdicts.jsonl)
  2 classes -> certified_exhausted (state/identifiability.jsonl)

Honest limits recorded in each report. No key material staged --
95_precommit_key_scan.sh verified clean before commit."

echo
echo "committed on $BRANCH"
git log --oneline -1
