"""
Six tools used by the 12-family distribution test.

Sandbox-safe: all paths resolve relative to a fixed root, cannot escape.
No network access. Each tool returns ToolResult(ok, output) where output
is JSON-ish text.

Registration is done by `register_all(registry)` called from
tools/__init__.py when AGI_TOOLS_FAMILIES=1.
"""
from __future__ import annotations

import csv
import difflib
import hashlib
import io
import json
import re
import sqlite3
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .base import Tool, ToolResult


def _resolve(root: Path, path: str) -> Path:
    if not path or path.startswith("/") or ".." in path.split("/"):
        raise ValueError(f"relative path required, no traversal: {path!r}")
    full = (root / path).resolve()
    try:
        full.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"path escapes root: {path}") from exc
    return full


# ---------- 1. csv_parse ----------
class _CSVArgs(BaseModel):
    path: str = Field(..., description="CSV file path")
    column: str | None = Field(None, description="Optional single column to summarize")


class CSVParseTool(Tool):
    args_model = _CSVArgs
    name = "csv_parse"
    description = (
        "Parse a CSV file. Returns row count, column names, and per-column stats: "
        "numeric columns get mean/min/max, text columns get unique-count."
    )

    def __init__(self, root: str):
        self.root = Path(root)

    def run(self, path: str, column: str | None = None) -> ToolResult:
        try:
            full = _resolve(self.root, path)
            if not full.exists():
                return ToolResult(ok=False, output=f"not found: {path}")
            text = full.read_text()
        except Exception as e:
            return ToolResult(ok=False, output=f"error: {e}")
        try:
            reader = csv.DictReader(io.StringIO(text))
            rows = list(reader)
            cols = reader.fieldnames or []
            if not rows:
                return ToolResult(ok=True, output="empty")

            def numeric(s):
                try:
                    float(s); return True
                except (ValueError, TypeError):
                    return False

            stats = {}
            for c in cols:
                if column is not None and c != column:
                    continue
                vals = [r.get(c, "") for r in rows]
                if all(numeric(v) or v == "" for v in vals):
                    nums = [float(v) for v in vals if v != ""]
                    if nums:
                        stats[c] = {
                            "type": "numeric", "count": len(nums),
                            "mean": sum(nums) / len(nums),
                            "min": min(nums), "max": max(nums),
                        }
                else:
                    stats[c] = {"type": "text", "count": len(vals), "unique": len(set(vals))}
            return ToolResult(ok=True, output=json.dumps(
                {"rows": len(rows), "columns": cols, "stats": stats}))
        except Exception as e:
            return ToolResult(ok=False, output=f"parse: {e}")


# ---------- 2. json_extract ----------
class _JXArgs(BaseModel):
    path: str = Field(..., description="JSON file path")
    key_path: str = Field(..., description="Dot-path like user.name or items[0].id")


class JSONExtractTool(Tool):
    args_model = _JXArgs
    name = "json_extract"
    description = "Extract a value from a JSON file at a dot-path. Supports list indices like items[0]."

    def __init__(self, root: str):
        self.root = Path(root)

    def run(self, path: str, key_path: str) -> ToolResult:
        try:
            full = _resolve(self.root, path)
            if not full.exists():
                return ToolResult(ok=False, output=f"not found: {path}")
            node: Any = json.loads(full.read_text())
        except Exception as e:
            return ToolResult(ok=False, output=f"error: {e}")
        try:
            for part in key_path.split("."):
                m = re.match(r"([A-Za-z0-9_]+)(?:\[(\d+)\])?$", part)
                if not m:
                    return ToolResult(ok=False, output=f"bad part: {part}")
                key, idx = m.group(1), m.group(2)
                if not isinstance(node, dict) or key not in node:
                    return ToolResult(ok=False, output=f"missing: {key}")
                node = node[key]
                if idx is not None:
                    if not isinstance(node, list) or int(idx) >= len(node):
                        return ToolResult(ok=False, output=f"bad idx at {part}")
                    node = node[int(idx)]
            return ToolResult(ok=True, output=json.dumps(node))
        except Exception as e:
            return ToolResult(ok=False, output=f"extract: {e}")


# ---------- 3. text_diff ----------
class _TDArgs(BaseModel):
    path_a: str = Field(..., description="First file")
    path_b: str = Field(..., description="Second file")


class TextDiffTool(Tool):
    args_model = _TDArgs
    name = "text_diff"
    description = "Line-level unified diff between two files. Returns diff text or 'identical'."

    def __init__(self, root: str):
        self.root = Path(root)

    def run(self, path_a: str, path_b: str) -> ToolResult:
        try:
            a = _resolve(self.root, path_a)
            b = _resolve(self.root, path_b)
            if not a.exists(): return ToolResult(ok=False, output=f"not found: {path_a}")
            if not b.exists(): return ToolResult(ok=False, output=f"not found: {path_b}")
            la = a.read_text().splitlines(keepends=True)
            lb = b.read_text().splitlines(keepends=True)
        except Exception as e:
            return ToolResult(ok=False, output=f"error: {e}")
        try:
            d = list(difflib.unified_diff(la, lb, fromfile=path_a, tofile=path_b))
            return ToolResult(ok=True, output="".join(d) or "identical")
        except Exception as e:
            return ToolResult(ok=False, output=f"diff: {e}")


# ---------- 4. text_regex ----------
class _TRArgs(BaseModel):
    path: str = Field(..., description="File to search")
    pattern: str = Field(..., description="Python regex")


class TextRegexTool(Tool):
    args_model = _TRArgs
    name = "text_regex"
    description = "Search a file for a Python regex pattern. Returns matching lines with 1-based line numbers."

    def __init__(self, root: str):
        self.root = Path(root)

    def run(self, path: str, pattern: str) -> ToolResult:
        try:
            full = _resolve(self.root, path)
            if not full.exists(): return ToolResult(ok=False, output=f"not found: {path}")
            text = full.read_text()
            rx = re.compile(pattern)
        except Exception as e:
            return ToolResult(ok=False, output=f"error: {e}")
        try:
            out = [{"line": i, "text": ln}
                   for i, ln in enumerate(text.splitlines(), 1) if rx.search(ln)]
            return ToolResult(ok=True, output=json.dumps(out))
        except Exception as e:
            return ToolResult(ok=False, output=f"search: {e}")


# ---------- 5. sqlite_query ----------
class _SQArgs(BaseModel):
    db_path: str = Field(..., description="SQLite DB file")
    sql: str = Field(..., description="SELECT/WITH/PRAGMA query")


class SQLiteQueryTool(Tool):
    args_model = _SQArgs
    name = "sqlite_query"
    description = "Run a read-only SQL query against a SQLite database. Returns rows as JSON."

    def __init__(self, root: str):
        self.root = Path(root)

    def run(self, db_path: str, sql: str) -> ToolResult:
        try:
            full = _resolve(self.root, db_path)
            if not full.exists(): return ToolResult(ok=False, output=f"not found: {db_path}")
            if not sql.strip().lower().startswith(("select", "with", "pragma")):
                return ToolResult(ok=False, output="only SELECT/WITH/PRAGMA")
        except Exception as e:
            return ToolResult(ok=False, output=f"error: {e}")
        try:
            conn = sqlite3.connect(str(full))
            conn.row_factory = sqlite3.Row
            rows = [dict(r) for r in conn.execute(sql).fetchall()]
            conn.close()
            return ToolResult(ok=True, output=json.dumps(rows))
        except Exception as e:
            return ToolResult(ok=False, output=f"query: {e}")


# ---------- 6. hash_check ----------
class _HCArgs(BaseModel):
    path: str = Field(..., description="File to hash")
    expected: str = Field(..., description="Expected SHA-256 hex digest")


class HashCheckTool(Tool):
    args_model = _HCArgs
    name = "hash_check"
    description = "Compare a file's SHA-256 against an expected hex digest. Returns 'match' or 'mismatch: <actual>'."

    def __init__(self, root: str):
        self.root = Path(root)

    def run(self, path: str, expected: str) -> ToolResult:
        try:
            full = _resolve(self.root, path)
            if not full.exists(): return ToolResult(ok=False, output=f"not found: {path}")
            actual = hashlib.sha256(full.read_bytes()).hexdigest()
        except Exception as e:
            return ToolResult(ok=False, output=f"error: {e}")
        return ToolResult(
            ok=True,
            output="match" if actual.lower() == expected.lower()
                            else f"mismatch: {actual}",
        )


def register_all(registry, fs_root: str | None = None) -> None:
    """Register all six family tools. Handles both dict-style and .register() registries."""
    root = str(fs_root or "state/workspace")
    tools = {
        "csv_parse": CSVParseTool(root),
        "json_extract": JSONExtractTool(root),
        "text_diff": TextDiffTool(root),
        "text_regex": TextRegexTool(root),
        "sqlite_query": SQLiteQueryTool(root),
        "hash_check": HashCheckTool(root),
    }
    if isinstance(registry, dict):
        registry.update(tools)
        return
    if hasattr(registry, "register"):
        for name, tool in tools.items():
            try:
                registry.register(tool)
            except TypeError:
                registry.register(name, tool)
        return
    raise TypeError(f"unsupported registry type: {type(registry)}")
