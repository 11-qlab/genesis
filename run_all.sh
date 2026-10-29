#!/usr/bin/env bash
# Usage: ./run_all.sh <model-id>
# Or:    MODEL=<model-id> ./run_all.sh
#
# Prereqs: stub_server.py running on :8088, OPENAI_BASE_URL + OPENAI_API_KEY set.
set -euo pipefail

M="${1:-${MODEL:-}}"
if [[ -z "$M" ]]; then
  echo "usage: $0 <model-id>   (or set MODEL env var)" >&2
  echo "examples: openai/gpt-oss-120b, qwen/qwen3.8-27b, allam-2-7b" >&2
  exit 2
fi

export MODEL="$M"
SAFE="${M//\//_}"

# Preflight 1: server
if ! curl -sf http://localhost:8088/status.json >/dev/null; then
  echo "ERROR: stub_server.py not reachable on :8088" >&2
  echo "  run: pkill -f stub_server.py; python3 stub_server.py &" >&2
  exit 3
fi

# Preflight 2: model reachable
python3 - <<'VERIFY_END_8q4v'
import os, sys
from openai import OpenAI
try:
    c = OpenAI(base_url=os.environ["OPENAI_BASE_URL"], api_key=os.environ["OPENAI_API_KEY"])
    r = c.chat.completions.create(model=os.environ["MODEL"], temperature=0,
                                  messages=[{"role": "user", "content": "ok"}])
    print("model ok:", r.model)
except Exception as e:
    print(f"ERROR: model {os.environ.get('MODEL')} not reachable: {e}", file=sys.stderr)
    print("  check: curl $OPENAI_BASE_URL/models -H \"Authorization: Bearer $OPENAI_API_KEY\"", file=sys.stderr)
    sys.exit(4)
VERIFY_END_8q4v

mkdir -p results
python3 seed_db.py

for fam in C D; do
  for cond in baseline prompt_patch executor_patch; do
    python3 run_family.py --family "$fam" --condition "$cond" --out "results/runs_${SAFE}.jsonl"
  done
done

python3 report.py "results/runs_${SAFE}.jsonl" | tee "results/report_${SAFE}.md"
python3 mcnemar.py "results/runs_${SAFE}.jsonl" | tee "results/mcnemar_${SAFE}.txt"
