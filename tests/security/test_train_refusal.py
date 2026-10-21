"""Training must refuse to start without --yes-train, from a clean env."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO / "src")
    return subprocess.run(
        [sys.executable, "-m", "agi", *args],
        cwd=cwd, env=env, capture_output=True, text=True, timeout=30,
    )


def test_train_run_refuses_without_flag(tmp_path: Path) -> None:
    ds = tmp_path / "ds.jsonl"
    ds.write_text('{"goal":"g","expect_tool":null}\n', encoding="utf-8")
    p = _run([
        "train", "run",
        "--name", "n",
        "--base-model", "m",
        "--dataset", str(ds),
    ], tmp_path)
    assert p.returncode == 2, p.stderr
    assert "refusing to start training without --yes-train" in p.stderr


def test_train_run_refuses_even_with_flag_without_adapter(tmp_path: Path) -> None:
    """--yes-train alone is not enough; no adapter is installed."""
    ds = tmp_path / "ds.jsonl"
    ds.write_text('{"goal":"g","expect_tool":null}\n', encoding="utf-8")
    p = _run([
        "train", "run",
        "--name", "n",
        "--base-model", "m",
        "--dataset", str(ds),
        "--yes-train",
    ], tmp_path)
    assert p.returncode == 2, p.stderr
    assert "no concrete training adapter is installed" in p.stderr.lower()


def test_train_estimate_does_not_touch_dataset(tmp_path: Path) -> None:
    p = _run([
        "train", "estimate",
        "--params-b", "0.1", "--tokens", "1000",
    ], tmp_path)
    assert p.returncode == 0, p.stderr
    assert "params_b" in p.stdout
