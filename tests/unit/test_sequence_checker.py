from __future__ import annotations

from agi.evaluation.benchmark import default_checker, tool_sequence_from_result
from agi.evaluation.dataset import DatasetItem


def _item(**raw) -> DatasetItem:
    base = {"goal": "g", "expect_tool": "fs_list"}
    base.update(raw)
    return DatasetItem(
        id="t", goal=base["goal"],
        expect_tool=base["expect_tool"], raw=base,
    )


def test_sequence_match():
    item = _item(expect_sequence=["fs_list", "fs_read"])
    ok, reason = default_checker(
        item, "succeeded", "fs_list", ("fs_list", "fs_read"),
    )
    assert ok, reason


def test_sequence_mismatch():
    item = _item(expect_sequence=["fs_list", "fs_read"])
    ok, reason = default_checker(
        item, "succeeded", "fs_list", ("fs_list",),
    )
    assert not ok
    assert "sequence" in reason


def test_sequence_absent_ignored():
    item = _item()
    ok, _ = default_checker(item, "succeeded", "fs_list", ("fs_list", "fs_read"))
    assert ok


def test_tool_sequence_from_result():
    result = {"results": [
        {"id": "a", "tool": "fs_list", "ok": True},
        {"id": "b", "tool": "fs_read", "ok": True},
    ]}
    assert tool_sequence_from_result(result) == ("fs_list", "fs_read")
