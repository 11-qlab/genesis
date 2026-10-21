#!/usr/bin/env bash
# F4 diagnostic — wrapper around scripts/diagnose_calibration_parse.py.
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

exec python3 scripts/diagnose_calibration_parse.py
