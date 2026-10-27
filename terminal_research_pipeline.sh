#!/usr/bin/env bash
set -uo pipefail

if [[ -z "${GROQ_API_KEY:-}" ]]; then
  read -rsp "Groq key: " GROQ_API_KEY; echo; export GROQ_API_KEY
fi
[[ -z "$GROQ_API_KEY" ]] && { echo "No key"; exit 1; }

export OPENAI_API_KEY="$GROQ_API_KEY"
export OPENAI_BASE_URL="https://api.groq.com/openai/v1"
export OPENAI_API_BASE="$OPENAI_BASE_URL"
export WT_TERMINUS_API_KEY="$GROQ_API_KEY"
export WT_TERMINUS_API_BASE="$OPENAI_BASE_URL"
export WT_TERMINUS_MODEL="openai/openai/gpt-oss-120b"

ROOT="$(pwd)"; WORK="$ROOT/tb_workspace"; VENV="$ROOT/.venv-tb"

command -v docker >/dev/null || { echo "docker missing"; exit 1; }
docker info >/dev/null 2>&1 || { echo "start docker: sudo systemctl start docker"; exit 1; }

if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi
uv python install 3.12
uv venv --python 3.12 "$VENV"
source "$VENV/bin/activate"
uv pip install --quiet --upgrade pip 'setuptools<82' wheel
uv pip install --quiet 'harbor>=0.1.28' 'agent-diagnostics>=0.8.1' 'pyarrow==17.0.0'

rm -rf "$WORK"; mkdir -p "$WORK/oracle" "$WORK/agent"
echo "── Oracle smoke test ───────────────────────────────────────────────"
( cd "$WORK/oracle" && harbor run -d terminal-bench@2.0 -a oracle -l 10 --n-concurrent 4 )

ORACLE_PASS=$(python3 - "$WORK/oracle" <<'PY'
import json, sys
from pathlib import Path
p=t=0
for f in Path(sys.argv[1]).rglob("result.json"):
    try: r=float(json.loads(f.read_text()).get("reward",0))
    except Exception: continue
    t+=1
    if r>=1.0: p+=1
print(f"{p}/{t}")
PY
)
echo "Oracle passed: $ORACLE_PASS"
[[ "$ORACLE_PASS" == 0/* ]] && { echo "oracle broke — abort"; exit 1; }

echo "── Agent run: terminus-2 + Groq ────────────────────────────────────"
( cd "$WORK/agent" && harbor run -d terminal-bench@2.0 -a terminus-2 -m "$WT_TERMINUS_MODEL" -l 10 --n-concurrent 2 )

RUNS="$ROOT/runs"; SIG="$ROOT/signals"
rm -rf "$RUNS" "$SIG"; mkdir -p "$RUNS" "$SIG"

python3 - "$WORK/agent" "$RUNS" "$WT_TERMINUS_MODEL" <<'PY'
import json, sys
from pathlib import Path
jr, rd, m = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
jobs = sorted([p for p in jr.rglob("jobs") if p.is_dir()], key=lambda p: p.stat().st_mtime)
if not jobs: raise SystemExit("no jobs")
for rp in jobs[-1].rglob("result.json"):
    try: r=json.loads(rp.read_text())
    except Exception: continue
    rw=r.get("reward", r.get("score"))
    if rw is None: continue
    task=r.get("task_id") or r.get("task_name") or rp.parent.name
    o=rd/f"{rp.parent.name}_{task}"; o.mkdir(parents=True, exist_ok=True)
    (o/"result.json").write_text(json.dumps({
        "task_name": str(task), "reward": float(rw), "passed": float(rw)>=1.0,
        "agent_info": {"name":"terminus-2"}, "model": m,
        "stdout": r.get("stdout","") or "", "stderr": r.get("stderr","") or "",
    }, indent=2))
    log = r.get("agent_output") or r.get("log") or r.get("stdout") or ""
    (o/"trajectory.json").write_text(json.dumps([
        {"role":"system","content":"TB 2.0"},
        {"role":"user","content":str(task)},
        {"role":"assistant","content":str(log)[-4000:]},
    ], indent=2))
PY

agent-diagnostics ingest --runs-dir "$RUNS" --output "$SIG/signals.jsonl"
agent-diagnostics annotate --signals "$SIG/signals.jsonl" --output "$SIG/heuristic.json"

echo "── Pass rate ───────────────────────────────────────────────────────"
agent-diagnostics query "
SELECT model, count(*) n,
       round(avg(CASE WHEN passed THEN 1.0 ELSE 0.0 END)*100,1) pass_rate
FROM signals GROUP BY model"

echo "✅ done — runs/, signals/"
