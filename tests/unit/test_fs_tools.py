from __future__ import annotations

from pathlib import Path

from agi.tools import FSListTool, FSReadTool, FSWriteTool


def test_write_read_list(workspace: Path) -> None:
    w = FSWriteTool(workspace)
    r = FSReadTool(workspace)
    listing = FSListTool(workspace)

    assert w.run(path="a.txt", content="hello", mode="overwrite").ok
    assert r.run(path="a.txt").output == "hello"
    assert "a.txt" in listing.run(path=".").output
    assert w.run(path="a.txt", content=" world", mode="append").ok
    assert r.run(path="a.txt").output == "hello world"


def test_missing_file(workspace: Path) -> None:
    r = FSReadTool(workspace)
    assert not r.run(path="missing.txt").ok


def test_not_a_directory(workspace: Path) -> None:
    FSWriteTool(workspace).run(path="f.txt", content="x", mode="overwrite")
    listing = FSListTool(workspace)
    assert not listing.run(path="f.txt").ok


def test_max_bytes(workspace: Path) -> None:
    FSWriteTool(workspace).run(path="big.txt", content="x" * 1000, mode="overwrite")
    r = FSReadTool(workspace)
    assert len(r.run(path="big.txt", max_bytes=10).output) == 10


def test_escape_rejected_write(workspace: Path) -> None:
    w = FSWriteTool(workspace)
    res = w.run(path="../../evil.txt", content="x", mode="overwrite")
    assert not res.ok
    assert "escapes" in res.output
