from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    # Strip any AGI_* vars that leaked from the caller's shell, so the
    # subprocess starts from the repo's config/default.toml only.
    for name in list(env):
        if name.startswith("AGI_"):
            del env[name]
    env["PYTHONPATH"] = str(REPO / "src")
    env["AGI_STORAGE_PATH"] = str(cwd / "state" / "cli.sqlite3")
    env["AGI_FS_ROOT"] = str(cwd / "ws")
    env["AGI_CONFIG"] = str(REPO / "config" / "default.toml")
    (cwd / "ws").mkdir(parents=True, exist_ok=True)
    return subprocess.run(
        [sys.executable, "-m", "agi", *args],
        cwd=cwd, env=env, capture_output=True, text=True, timeout=60,
    )


def test_version(tmp_path: Path) -> None:
    p = _run(["version"], tmp_path)
    assert p.returncode == 0, p.stderr
    assert "agi" in p.stdout


def test_doctor(tmp_path: Path) -> None:
    p = _run(["doctor"], tmp_path)
    assert p.returncode == 0, p.stderr
    payload = json.loads(p.stdout)
    assert payload["provider"]["kind"] == "echo"


def test_run_and_show(tmp_path: Path) -> None:
    p = _run(["run", "list workspace"], tmp_path)
    assert p.returncode == 0, p.stderr
    result = json.loads(p.stdout)
    assert result["status"] == "succeeded"

    p = _run(["runs"], tmp_path)
    assert p.returncode == 0, p.stderr
    assert "succeeded" in p.stdout

    p = _run(["show", str(result["run_id"])], tmp_path)
    assert p.returncode == 0, p.stderr
