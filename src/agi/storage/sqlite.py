"""SQLite-backed run and event store."""

from __future__ import annotations

import contextlib
import json
import sqlite3
import time
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    goal TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    status TEXT NOT NULL,
    summary TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_run ON events(run_id, id);

CREATE TABLE IF NOT EXISTS eval_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    benchmark TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    status TEXT NOT NULL,
    total INTEGER NOT NULL,
    passed INTEGER NOT NULL,
    accuracy REAL NOT NULL,
    duration_ms REAL NOT NULL,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS eval_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    eval_run_id INTEGER NOT NULL REFERENCES eval_runs(id) ON DELETE CASCADE,
    item_id TEXT NOT NULL,
    goal TEXT NOT NULL,
    status TEXT NOT NULL,
    passed INTEGER NOT NULL,
    tool_used TEXT,
    expect_tool TEXT,
    duration_ms REAL NOT NULL,
    run_id INTEGER,
    detail TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_eval_items_run ON eval_items(eval_run_id, id);

CREATE TABLE IF NOT EXISTS memory_documents (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    title TEXT NOT NULL,
    text TEXT NOT NULL,
    metadata TEXT NOT NULL DEFAULT '{}',
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS memory_chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id TEXT NOT NULL REFERENCES memory_documents(id) ON DELETE CASCADE,
    idx INTEGER NOT NULL,
    text TEXT NOT NULL,
    offset INTEGER NOT NULL,
    embedding BLOB NOT NULL,
    embedding_dim INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_memory_chunks_doc ON memory_chunks(document_id, idx);
"""


class Store:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()
        self._ensure_contaminated_column()

    def _ensure_contaminated_column(self) -> None:
        """Add `contaminated` to eval_runs if missing (additive migration)."""
        cols = [
            row[1] for row in
            self._conn.execute("PRAGMA table_info(eval_runs)").fetchall()
        ]
        if "contaminated" not in cols:
            self._conn.execute(
                "ALTER TABLE eval_runs ADD COLUMN contaminated INTEGER NOT NULL DEFAULT 0"
            )
            self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def create_run(self, goal: str, provider: str, model: str) -> int:
        now = time.time()
        cursor = self._conn.execute(
            "INSERT INTO runs(goal, provider, model, status, created_at, updated_at) "
            "VALUES (?, ?, ?, 'running', ?, ?)",
            (goal, provider, model, now, now),
        )
        self._conn.commit()
        return int(cursor.lastrowid)

    def finish_run(self, run_id: int, status: str, summary: str | None = None) -> None:
        self._conn.execute(
            "UPDATE runs SET status=?, summary=?, updated_at=? WHERE id=?",
            (status, summary, time.time(), run_id),
        )
        self._conn.commit()

    def get_run(self, run_id: int) -> dict[str, Any] | None:
        row = self._conn.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        return dict(row) if row else None

    def list_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM runs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(row) for row in rows]

    def add_event(self, run_id: int, kind: str, payload: dict[str, Any]) -> int:
        cursor = self._conn.execute(
            "INSERT INTO events(run_id, kind, payload, created_at) VALUES (?, ?, ?, ?)",
            (run_id, kind, json.dumps(payload, ensure_ascii=False), time.time()),
        )
        self._conn.commit()
        return int(cursor.lastrowid)

    def list_events(self, run_id: int) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM events WHERE run_id=? ORDER BY id", (run_id,)
        ).fetchall()
        events: list[dict[str, Any]] = []
        for row in rows:
            event = dict(row)
            with contextlib.suppress(json.JSONDecodeError):
                event["payload"] = json.loads(event["payload"])
            events.append(event)
        return events

    # --- evaluation ----------------------------------------------------

    def create_eval_run(
        self, benchmark: str, provider: str, model: str, total: int
    ) -> int:
        now = time.time()
        cursor = self._conn.execute(
            "INSERT INTO eval_runs(benchmark, provider, model, status, "
            "total, passed, accuracy, duration_ms, created_at) "
            "VALUES (?, ?, ?, 'running', ?, 0, 0.0, 0.0, ?)",
            (benchmark, provider, model, total, now),
        )
        self._conn.commit()
        return int(cursor.lastrowid)

    def finish_eval_run(
        self,
        eval_run_id: int,
        *,
        status: str,
        total: int,
        passed: int,
        duration_ms: float,
        contaminated: bool = False,
    ) -> None:
        accuracy = (passed / total) if total else 0.0
        self._conn.execute(
            "UPDATE eval_runs SET status=?, total=?, passed=?, accuracy=?, "
            "duration_ms=?, contaminated=? WHERE id=?",
            (status, total, passed, accuracy, duration_ms,
             1 if contaminated else 0, eval_run_id),
        )
        self._conn.commit()

    def add_eval_item(
        self,
        eval_run_id: int,
        *,
        item_id: str,
        goal: str,
        status: str,
        passed: bool,
        tool_used: str | None,
        expect_tool: str | None,
        duration_ms: float,
        run_id: int | None,
        detail: str = "",
    ) -> int:
        cursor = self._conn.execute(
            "INSERT INTO eval_items(eval_run_id, item_id, goal, status, "
            "passed, tool_used, expect_tool, duration_ms, run_id, detail) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                eval_run_id, item_id, goal, status, int(passed),
                tool_used, expect_tool, duration_ms, run_id, detail,
            ),
        )
        self._conn.commit()
        return int(cursor.lastrowid)

    def get_eval_run(self, eval_run_id: int) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM eval_runs WHERE id=?", (eval_run_id,)
        ).fetchone()
        return dict(row) if row else None

    def list_eval_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM eval_runs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(row) for row in rows]

    def list_eval_items(self, eval_run_id: int) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM eval_items WHERE eval_run_id=? ORDER BY id",
            (eval_run_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    # --- memory ---------------------------------------------------------

    def add_memory_document(
        self, *, doc_id: str, source: str, title: str,
        text: str, metadata: str,
    ) -> None:
        self._conn.execute(
            "INSERT INTO memory_documents(id, source, title, text, metadata, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (doc_id, source, title, text, metadata, time.time()),
        )
        self._conn.commit()

    def get_memory_document(self, doc_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM memory_documents WHERE id=?", (doc_id,)
        ).fetchone()
        return dict(row) if row else None

    def list_memory_documents(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT id, source, title, created_at FROM memory_documents ORDER BY created_at"
        ).fetchall()
        return [dict(row) for row in rows]

    def add_memory_chunk(
        self, *, document_id: str, idx: int, text: str,
        offset: int, embedding: bytes, embedding_dim: int,
    ) -> int:
        cur = self._conn.execute(
            "INSERT INTO memory_chunks(document_id, idx, text, offset, embedding, embedding_dim) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (document_id, idx, text, offset, embedding, embedding_dim),
        )
        self._conn.commit()
        return int(cur.lastrowid)

    def list_memory_chunks(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM memory_chunks ORDER BY id"
        ).fetchall()
        return [dict(row) for row in rows]
