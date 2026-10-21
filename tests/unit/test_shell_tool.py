from __future__ import annotations

from agi.tools import ShellTool


def test_allowed_echo() -> None:
    tool = ShellTool(["echo"], 5)
    res = tool.run(command="echo hi")
    assert res.ok
    assert "hi" in res.output


def test_disallowed_command() -> None:
    tool = ShellTool(["echo"], 5)
    res = tool.run(command="rm -rf /")
    assert not res.ok
    assert "not allowed" in res.output


def test_bad_syntax() -> None:
    tool = ShellTool(["echo"], 5)
    res = tool.run(command="echo 'unbalanced")
    assert not res.ok
    assert "parse" in res.output


def test_empty() -> None:
    tool = ShellTool(["echo"], 5)
    res = tool.run(command="")
    assert not res.ok


def test_nonzero_exit() -> None:
    tool = ShellTool(["false"], 5)
    res = tool.run(command="false")
    assert not res.ok
    assert res.meta["returncode"] != 0
