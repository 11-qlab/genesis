from __future__ import annotations

import json
from pathlib import Path

import pytest

from agi.evaluation.dataset import DatasetError, load_dataset


def _write(path: Path, lines: list[dict]) -> Path:
    path.write_text("\n".join(json.dumps(x) for x in lines) + "\n", encoding="utf-8")
    return path


def test_load_ok(tmp_path: Path) -> None:
    p = _write(tmp_path / "ds.jsonl", [
        {"id": "a", "goal": "g1", "expect_tool": "fs_list"},
        {"goal": "g2", "expect_tool": None},
    ])
    ds = load_dataset(p)
    assert len(ds) == 2
    assert ds.items[0].id == "a"
    assert ds.items[1].id == "item-2"
    assert ds.items[1].expect_tool is None


def test_blank_and_comment_lines(tmp_path: Path) -> None:
    p = tmp_path / "ds.jsonl"
    p.write_text(
        "\n# a comment\n"
        + json.dumps({"goal": "g", "expect_tool": "fs_list"}) + "\n",
        encoding="utf-8",
    )
    ds = load_dataset(p)
    assert len(ds) == 1


def test_missing_goal(tmp_path: Path) -> None:
    p = _write(tmp_path / "ds.jsonl", [{"expect_tool": "fs_list"}])
    with pytest.raises(DatasetError):
        load_dataset(p)


def test_missing_expect_tool(tmp_path: Path) -> None:
    p = _write(tmp_path / "ds.jsonl", [{"goal": "g"}])
    with pytest.raises(DatasetError):
        load_dataset(p)


def test_bad_status(tmp_path: Path) -> None:
    p = _write(tmp_path / "ds.jsonl",
               [{"goal": "g", "expect_tool": None, "expect_status": "weird"}])
    with pytest.raises(DatasetError):
        load_dataset(p)


def test_empty_file(tmp_path: Path) -> None:
    p = tmp_path / "ds.jsonl"
    p.write_text("", encoding="utf-8")
    with pytest.raises(DatasetError):
        load_dataset(p)


def test_missing_file(tmp_path: Path) -> None:
    with pytest.raises(DatasetError):
        load_dataset(tmp_path / "nope.jsonl")
