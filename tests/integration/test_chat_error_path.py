"""Point AGI_BASE_URL at nothing; chat must exit 1 with a clean message,
not a rich traceback."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def test_chat_fails_cleanly(tmp_path: Path) -> None:
    env = os.environ.copy()
    env.update({
        "PYTHONPATH": str(REPO / "src"),
        "AGI_PROVIDER_KIND": "openai_compat",
        "AGI_BASE_URL": "http://127.0.0.1:1/v1",
        "AGI_MODEL": "m",
        "AGI_PROVIDER_TIMEOUT_S": "2",
        "AGI_PROVIDER_MAX_RETRIES": "0",
        "AGI_STORAGE_PATH": str(tmp_path / "s.sqlite3"),
        "AGI_FS_ROOT": str(tmp_path / "ws"),
    })
    (tmp_path / "ws").mkdir(parents=True, exist_ok=True)
    p = subprocess.run(
        [sys.executable, "-m", "agi", "chat", "hi"],
        cwd=REPO, env=env, capture_output=True, text=True, timeout=30,
    )
    assert p.returncode == 1, (p.returncode, p.stdout, p.stderr)
    combined = (p.stdout + p.stderr).lower()
    assert "chat failed" in combined
    assert "traceback" not in combined
