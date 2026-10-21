from __future__ import annotations

from pathlib import Path

from agi.reasoning import Plan, PlanStep
from agi.trajectories.t5_memory import (
    EpisodicMemory,
    format_prior_examples,
)


def _plan(tool: str = "fs_list") -> Plan:
    return Plan(goal="g", steps=[
        PlanStep(id="s1", title="t", tool=tool, args={"path": "."}),
    ])


def test_record_and_retrieve(tmp_path: Path) -> None:
    mem = EpisodicMemory(tmp_path / "e.sqlite3")
    try:
        mem.record("list the workspace", _plan(), success=True)
        mem.record("read a file", _plan("fs_read"), success=True)
        mem.record("list the files", _plan(), success=True)
        hits = mem.retrieve_similar("list everything in the workspace", k=2)
        assert hits
        goals = [h[0].goal for h in hits]
        assert "list the workspace" in goals or "list the files" in goals
    finally:
        mem.close()


def test_only_successful_by_default(tmp_path: Path) -> None:
    mem = EpisodicMemory(tmp_path / "e.sqlite3")
    try:
        mem.record("list x", _plan(), success=False)
        mem.record("list x again", _plan(), success=True)
        hits = mem.retrieve_similar("list x", k=5)
        assert all(e.success for e, _ in hits)
    finally:
        mem.close()


def test_include_failures_when_asked(tmp_path: Path) -> None:
    mem = EpisodicMemory(tmp_path / "e.sqlite3")
    try:
        mem.record("list x", _plan(), success=False)
        hits = mem.retrieve_similar("list x", k=5, only_successful=False)
        assert len(hits) == 1 and not hits[0][0].success
    finally:
        mem.close()


def test_format_prior_examples(tmp_path: Path) -> None:
    mem = EpisodicMemory(tmp_path / "e.sqlite3")
    try:
        mem.record("list the workspace", _plan(), success=True)
        hits = mem.retrieve_similar("list everything", k=1)
        text = format_prior_examples(hits)
        assert "list the workspace" in text
        assert "fs_list" in text
    finally:
        mem.close()
