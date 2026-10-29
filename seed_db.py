#!/usr/bin/env python3
"""Deterministic seed data so sql_query returns stable observations."""
import os, sqlite3, random
from pathlib import Path

DB = os.environ.get("SHIM_DB", "shim.db")
Path(DB).unlink(missing_ok=True)
con = sqlite3.connect(DB)
con.executescript("""
CREATE TABLE events(day TEXT, kind TEXT);
CREATE TABLE sessions(ts TEXT);
CREATE TABLE sales(region TEXT, amount REAL);
CREATE TABLE logins(user TEXT);
CREATE TABLE requests(latency_ms REAL);
""")
# 17 events on 2024-01-01
con.executemany("INSERT INTO events VALUES (?,?)",
    [("2024-01-01", "click")] * 17)
# max(ts) deterministic
con.executemany("INSERT INTO sessions VALUES (?)",
    [("2024-03-15T09:42:11Z",), ("2024-03-14T08:00:00Z",), ("2024-03-13T11:11:11Z",)])
# sales: east=1200, west=950
con.executemany("INSERT INTO sales VALUES (?,?)",
    [("east", 1200.0), ("west", 950.0)])
# 42 distinct users
con.executemany("INSERT INTO logins VALUES (?)",
    [(f"u{i:03d}",) for i in range(42)])
# latency avg = 87.3
con.executemany("INSERT INTO requests VALUES (?)",
    [(80.0,), (90.0,), (92.0,)])
con.commit()
con.close()
print(f"seeded {DB}")
