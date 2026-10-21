"""Alias tests go through ToolRegistry.execute — the real production path.

`ToolRegistry.execute` runs `args_model(**args)`, which triggers the
field_validator on mode. Calling `FSWriteTool.run` directly bypasses it,
which is what an earlier version of this test file accidentally did.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agi.core.errors import ToolError
from agi.tools import FSReadTool, build_registry


def _write(workspace: Path, mode: str, content: str) -> None:
    reg = build_registry(["fs_write"], str(workspace))
    result = reg.execute("fs_write", {"path": "f.txt", "content": content, "mode": mode})
    assert result.ok, result.output


def test_aliases_w_a(workspace: Path) -> None:
    _write(workspace, "w", "first")
    assert FSReadTool(workspace).run(path="f.txt").output == "first"
    _write(workspace, "a", " second")
    assert FSReadTool(workspace).run(path="f.txt").output == "first second"


def test_aliases_write_append(workspace: Path) -> None:
    _write(workspace, "write", "x")
    _write(workspace, "append", "y")
    assert FSReadTool(workspace).run(path="f.txt").output == "xy"


def test_aliases_create_truncate(workspace: Path) -> None:
    _write(workspace, "create", "abc")
    _write(workspace, "truncate", "z")
    assert FSReadTool(workspace).run(path="f.txt").output == "z"


def test_case_insensitive(workspace: Path) -> None:
    _write(workspace, "W", "x")
    _write(workspace, "Append", "y")
    assert FSReadTool(workspace).run(path="f.txt").output == "xy"


def test_unknown_mode_rejected(workspace: Path) -> None:
    reg = build_registry(["fs_write"], str(workspace))
    with pytest.raises(ToolError):
        reg.execute("fs_write", {"path": "f.txt", "content": "x", "mode": "nope"})


def test_none_mode_rejected(workspace: Path) -> None:
    reg = build_registry(["fs_write"], str(workspace))
    with pytest.raises(ToolError):
        reg.execute("fs_write", {"path": "f.txt", "content": "x", "mode": None})
