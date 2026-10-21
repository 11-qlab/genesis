from __future__ import annotations

from agi.evaluation.benchmark import (
    _contains_subsequence,
    default_checker,
    tool_sequence_from_result,
)
from agi.evaluation.dataset import DatasetItem


def _item(**raw) -> DatasetItem:
    base = {"goal": "g", "expect_tool": None}
    base.update(raw)
    return DatasetItem(
        id="t", goal=base["goal"], expect_tool=base["expect_tool"], raw=base,
    )


def test_contains_subsequence_basic():
    assert _contains_subsequence([1, 2, 3, 4], [1, 3])
    assert _contains_subsequence([1, 2, 3, 4], [4])
    assert not _contains_subsequence([1, 2, 3], [4])
    assert not _contains_subsequence([1, 3], [1, 2, 3])


def test_expect_subsequence_passes():
    item = _item(expect_subsequence=["fs_read", "fs_write", "fs_read"])
    ok, reason = default_checker(
        item, "succeeded", "fs_read",
        ("fs_read", "fs_write", "fs_read", "fs_write"),
    )
    assert ok, reason


def test_expect_subsequence_fails():
    item = _item(expect_subsequence=["fs_read", "fs_write", "fs_read"])
    ok, reason = default_checker(
        item, "succeeded", "fs_read", ("fs_read", "fs_read"),
    )
    assert not ok
    assert "subsequence" in reason


def test_tool_sequence_uses_tools_invoked():
    result = {"results": [
        {"id": "a", "tool": "fs_read", "tools_invoked": ["fs_read", "fs_write", "fs_read"]},
        {"id": "b", "tool": "fs_list", "tools_invoked": ["fs_list"]},
    ]}
    assert tool_sequence_from_result(result) == (
        "fs_read", "fs_write", "fs_read", "fs_list",
    )


def test_tool_sequence_falls_back_to_tool():
    result = {"results": [
        {"id": "a", "tool": "fs_read"},
        {"id": "b", "tool": "fs_list"},
    ]}
    assert tool_sequence_from_result(result) == ("fs_read", "fs_list")
