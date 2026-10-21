#!/usr/bin/env bash
# Verify the environment is ready. Does not install anything.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "python: $(python3 --version)"
python3 - <<'PY'
import importlib.util, sys
missing = [m for m in ("pydantic", "typer", "rich", "pytest") if importlib.util.find_spec(m) is None]
if missing:
    print("missing modules:", missing); sys.exit(1)
print("required modules present")
PY

echo "running: pytest -q"
python3 -m pytest -q --no-header

echo "running: ruff check src tests"
ruff check src tests

echo "running: doctor"
PYTHONPATH=src python3 -m agi doctor >/dev/null
echo "setup OK"
