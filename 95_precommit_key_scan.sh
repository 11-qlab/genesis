#!/usr/bin/env bash
# 95_precommit_key_scan.sh — refuse to commit if any API key is exposed.
# Scans every file that `git add -A` would stage. Exits 1 if a key is found.
set -euo pipefail
cd "$(dirname "$0")"

echo "=== scanning for exposed credentials ==="
PATTERNS='gsk_[A-Za-z0-9]{20,}|AQ\.Ab8RN[A-Za-z0-9_-]{20,}|AIza[A-Za-z0-9_-]{30,}'

# Build the candidate list from what git would actually stage
mapfile -t FILES < <(
  { git diff --name-only --cached 2>/dev/null;
    git diff --name-only 2>/dev/null;
    git ls-files --others --exclude-standard 2>/dev/null; } | sort -u
)

if [[ ${#FILES[@]} -eq 0 ]]; then
  echo "no files staged or untracked — nothing to scan"
  exit 0
fi

hits=0
for f in "${FILES[@]}"; do
  [[ -f "$f" ]] || continue
  case "$f" in
    *.log|*__pycache__*|*.pyc) continue ;;
  esac
  if grep -qE "$PATTERNS" "$f" 2>/dev/null; then
    echo "LEAK in $f:"
    grep -nE "$PATTERNS" "$f" | sed 's/=.*/=<REDACTED>/' | head -3
    hits=$((hits+1))
  fi
done

if [[ $hits -gt 0 ]]; then
  echo
  echo "BLOCK: $hits file(s) contain live credentials. Refusing to stage."
  echo "Fix: for each file, replace the key with \$GROQ_API_KEY or a placeholder."
  exit 1
fi
echo "clean — no key patterns found in staging candidates"
