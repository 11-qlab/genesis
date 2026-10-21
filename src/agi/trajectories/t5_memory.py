"""T5 — Episodic memory.

T5 in the trajectory map is "continual learning". Weight-level continual
learning requires training (see T1). What is buildable here is the
*episodic* subset: a persistent store of (goal, plan, outcome) tuples that
can be retrieved by goal similarity on subsequent runs.

This is not continual learning in the catastrophic-forgetting sense. It is
memory retrieval over past runs. The honest claim it can support:

    "Given k similar past goals and their outcomes, does the planner
     produce a better plan than without that context?"

That is a testable question. Whether the answer is yes for a given model
and benchmark is what the experiment would measure.

The default is opt-in: `EpisodicMemory` is a standalone class. Nothing in
`Planner` uses it unless a caller passes `prior_examples=...`. This keeps
D016 (prompt-tuning) out of the current benchmark scores.
"""

from __future__ import annotations

import json
import re
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path

from ..reasoning.schemas import Plan

_WORD = re.compile(r"[a-zA-Z][a-zA-Z0-9_]+")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS episodic_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    goal TEXT NOT NULL,
    plan_json TEXT NOT NULL,
    success INTEGER NOT NULL,
    tags TEXT NOT NULL DEFAULT '[]',
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_episodic_created ON episodic_memory(created_at DESC);
"""


@dataclass
class EpisodicEntry:
    goal: str
    plan: Plan
    success: bool
    tags: tuple[str, ...] = ()
    created_at: float = field(default_factory=time.time)
    id: int | None = None


def _tokens(text: str) -> set[str]:
    return {t.lower() for t in _WORD.findall(text)}


def _jaccard(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


class EpisodicMemory:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def record(
        self,
        goal: str,
        plan: Plan,
        *,
        success: bool,
        tags: list[str] | None = None,
    ) -> int:
        cursor = self._conn.execute(
            "INSERT INTO episodic_memory(goal, plan_json, success, tags, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                goal, json.dumps(plan.model_dump()),
                1 if success else 0,
                json.dumps(tags or []), time.time(),
            ),
        )
        self._conn.commit()
        return int(cursor.lastrowid)

    def list_all(self) -> list[EpisodicEntry]:
        rows = self._conn.execute(
            "SELECT id, goal, plan_json, success, tags, created_at "
            "FROM episodic_memory ORDER BY created_at DESC"
        ).fetchall()
        out: list[EpisodicEntry] = []
        for row in rows:
            try:
                plan = Plan.model_validate(json.loads(row["plan_json"]))
            except Exception:
                continue
            out.append(EpisodicEntry(
                goal=row["goal"], plan=plan,
                success=bool(row["success"]),
                tags=tuple(json.loads(row["tags"] or "[]")),
                created_at=row["created_at"], id=row["id"],
            ))
        return out

    def retrieve_similar(
        self,
        goal: str,
        *,
        k: int = 3,
        only_successful: bool = True,
    ) -> list[tuple[EpisodicEntry, float]]:
        """Return up to k past entries ranked by goal-similarity (Jaccard)."""
        entries = self.list_all()
        if only_successful:
            entries = [e for e in entries if e.success]
        scored = [(e, _jaccard(goal, e.goal)) for e in entries]
        scored = [x for x in scored if x[1] > 0.0]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:k]


def format_prior_examples(
    examples: list[tuple[EpisodicEntry, float]],
) -> str:
    """Format retrieved examples as a prompt-augmentable string.

    Callers who want to use this must pass the returned string to
    `Planner.plan(..., prior_context=...)`. The default `Planner` does not
    read this on its own, so existing benchmark scores are unchanged.
    """
    if not examples:
        return ""
    lines = ["Similar past tasks and their results:"]
    for entry, score in examples:
        lines.append(
            f"- goal: {entry.goal!r} (similarity={score:.2f}); "
            f"success={entry.success}; "
            f"tools_used={[s.tool for s in entry.plan.steps]}"
        )
    return "\n".join(lines) + "\n\n"
