from __future__ import annotations

from pathlib import Path

import pytest

from agi.evaluation.compare import CompareError, compare_runs
from agi.storage import Store


def _seed(store: Store, rows: list[tuple[str, bool, str | None]]) -> int:
    rid = store.create_eval_run("bench", "echo", "echo-1", len(rows))
    passed = sum(1 for _, p, _ in rows if p)
    for item_id, p, tool in rows:
        store.add_eval_item(
            rid, item_id=item_id, goal="g", status="succeeded",
            passed=p, tool_used=tool, expect_tool="fs_list",
            duration_ms=1.0, run_id=None, detail="",
        )
    store.finish_eval_run(rid, status="completed", total=len(rows),
                          passed=passed, duration_ms=1.0)
    return rid


def test_delta_and_regressions(tmp_path: Path) -> None:
    s = Store(tmp_path / "c.sqlite3")
    try:
        a = _seed(s, [("x", True, "fs_list"), ("y", True, "fs_list"), ("z", False, None)])
        b = _seed(s, [("x", True, "fs_list"), ("y", False, "fs_list"), ("z", True, "fs_list")])
        out = compare_runs(s, a, b)
        assert out["delta_accuracy"] == pytest.approx(0.0)
        assert out["delta_passed"] == 0
        assert out["shared_items"] == 3
        assert out["regressions"] == ["y"]
        assert out["improvements"] == ["z"]
        assert out["stable_pass"] == 1
        assert out["stable_fail"] == 0
    finally:
        s.close()


def test_tool_changes(tmp_path: Path) -> None:
    s = Store(tmp_path / "c.sqlite3")
    try:
        a = _seed(s, [("x", True, "fs_list")])
        b = _seed(s, [("x", True, "fs_read")])
        out = compare_runs(s, a, b)
        assert out["tool_changes"] == [
            {"item_id": "x", "tool_a": "fs_list", "tool_b": "fs_read"}
        ]
    finally:
        s.close()


def test_only_in_one_side(tmp_path: Path) -> None:
    s = Store(tmp_path / "c.sqlite3")
    try:
        a = _seed(s, [("x", True, "fs_list"), ("only-a", True, "fs_list")])
        b = _seed(s, [("x", True, "fs_list"), ("only-b", True, "fs_list")])
        out = compare_runs(s, a, b)
        assert out["only_in_a"] == ["only-a"]
        assert out["only_in_b"] == ["only-b"]
    finally:
        s.close()


def test_missing_and_same_id_raise(tmp_path: Path) -> None:
    s = Store(tmp_path / "c.sqlite3")
    try:
        a = _seed(s, [("x", True, "fs_list")])
        with pytest.raises(CompareError):
            compare_runs(s, a, a)
        with pytest.raises(CompareError):
            compare_runs(s, a, 9999)
    finally:
        s.close()
