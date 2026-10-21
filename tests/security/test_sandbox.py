from __future__ import annotations

from pathlib import Path

from agi.tools import FSListTool, FSReadTool, FSWriteTool, ShellTool


def test_escape_write(workspace: Path) -> None:
    w = FSWriteTool(workspace)
    assert not w.run(path="../../etc/x", content="x", mode="overwrite").ok
    assert not w.run(path="/etc/x", content="x", mode="overwrite").ok


def test_escape_read(workspace: Path) -> None:
    r = FSReadTool(workspace)
    assert not r.run(path="../../etc/passwd").ok
    assert not r.run(path="/etc/passwd").ok


def test_escape_list(workspace: Path) -> None:
    listing = FSListTool(workspace)
    assert not listing.run(path="..").ok
    assert not listing.run(path="/").ok


def test_shell_rejects_unlisted() -> None:
    t = ShellTool(["echo"], 5)
    for cmd in ["rm", "sh", "bash", "python", "curl", "wget"]:
        res = t.run(command=cmd)
        assert not res.ok, f"{cmd} should not run"
        assert "not allowed" in res.output


def test_shell_rejects_pipe_metachars() -> None:
    t = ShellTool(["echo"], 5)
    res = t.run(command="echo hi | rm -rf /")
    # No shell → '|' is passed as a literal arg to echo; the 'rm' never runs.
    assert res.ok
    assert "|" in res.output
