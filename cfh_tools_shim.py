"""Real, deterministic tool dispatch for families C and D.

- sql_query executes against a real SQLite file (see seed_db.py)
- fs_write actually writes to disk under ./out/
- http_get calls a real local server (see stub_server.py)
Returns the observation as a string.
"""
from __future__ import annotations
import os, sqlite3, urllib.request
from pathlib import Path

DB_PATH = os.environ.get("SHIM_DB", "shim.db")
OUT_DIR = Path("out")

def _sql_query(q: str) -> str:
    con = sqlite3.connect(DB_PATH)
    try:
        cur = con.execute(q)
        rows = cur.fetchall()
    finally:
        con.close()
    if len(rows) == 1 and len(rows[0]) == 1:
        return str(rows[0][0])
    return str(rows)

def _fs_write(path: str, content: str) -> str:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"wrote {len(content)}B to {path}"

def _http_get(url: str) -> str:
    with urllib.request.urlopen(url, timeout=5) as resp:
        return resp.read().decode("utf-8", errors="replace")

def dispatch(tool: str, args: dict) -> str:
    if tool == "sql_query":
        return _sql_query(args["q"])
    if tool == "fs_write":
        return _fs_write(args["path"], args["content"])
    if tool == "http_get":
        return _http_get(args["url"])
    raise KeyError(f"unknown tool: {tool}")
