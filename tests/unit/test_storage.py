from __future__ import annotations

from pathlib import Path

from agi.storage import Store


def test_run_lifecycle(tmp_path: Path) -> None:
    s = Store(tmp_path / "s.sqlite3")
    try:
        rid = s.create_run("goal", "echo", "echo-1")
        assert rid >= 1
        s.add_event(rid, "custom", {"a": 1})
        s.finish_run(rid, "succeeded", "ok")
        run = s.get_run(rid)
        assert run and run["status"] == "succeeded"
        events = s.list_events(rid)
        assert len(events) == 1 and events[0]["kind"] == "custom"
        assert events[0]["payload"] == {"a": 1}
    finally:
        s.close()


def test_list_runs_order(tmp_path: Path) -> None:
    s = Store(tmp_path / "s.sqlite3")
    try:
        id1 = s.create_run("g1", "echo", "m")
        id2 = s.create_run("g2", "echo", "m")
        ids = [r["id"] for r in s.list_runs(10)]
        assert ids == [id2, id1]
    finally:
        s.close()


def test_get_missing(tmp_path: Path) -> None:
    s = Store(tmp_path / "s.sqlite3")
    try:
        assert s.get_run(999) is None
    finally:
        s.close()
