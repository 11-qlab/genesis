"""Cross-tool substitution task families C, D. 10 tasks each."""
from __future__ import annotations
import json

FAMILY_C = [
    {"id": "C01", "steps": [
        {"tool": "sql_query", "args": {"q": "select count(*) from events where day='2024-01-01'"}},
        {"tool": "fs_write", "args": {"path": "reports/c01.md", "content": "<COUNT_PLACEHOLDER>"},
         "expect_arg": ("content", "prev_observation")}]},
    {"id": "C02", "steps": [
        {"tool": "sql_query", "args": {"q": "select max(ts) from sessions"}},
        {"tool": "fs_write", "args": {"path": "reports/c02.md", "content": "<TS_PLACEHOLDER>"},
         "expect_arg": ("content", "prev_observation")}]},
    {"id": "C03", "steps": [
        {"tool": "sql_query", "args": {"q": "select region, sum(amount) from sales group by region"}},
        {"tool": "fs_write", "args": {"path": "reports/c03.md", "content": "<ROWS_PLACEHOLDER>"},
         "expect_arg": ("content", "prev_observation")}]},
    {"id": "C04", "steps": [
        {"tool": "sql_query", "args": {"q": "select count(distinct user) from logins"}},
        {"tool": "fs_write", "args": {"path": "reports/c04.md", "content": "<N_PLACEHOLDER>"},
         "expect_arg": ("content", "prev_observation")}]},
    {"id": "C05", "steps": [
        {"tool": "sql_query", "args": {"q": "select avg(latency_ms) from requests"}},
        {"tool": "fs_write", "args": {"path": "reports/c05.md", "content": "<AVG_PLACEHOLDER>"},
         "expect_arg": ("content", "prev_observation")}]},
    {"id": "C06", "steps": [
        {"tool": "sql_query", "args": {"q": "select count(*) from events where day='2024-01-01'"}},
        {"tool": "fs_write", "args": {"path": "reports/c06.md", "content": "<EV_PLACEHOLDER>"},
         "expect_arg": ("content", "prev_observation")}]},
    {"id": "C07", "steps": [
        {"tool": "sql_query", "args": {"q": "select max(ts) from sessions"}},
        {"tool": "fs_write", "args": {"path": "reports/c07.md", "content": "<TS2_PLACEHOLDER>"},
         "expect_arg": ("content", "prev_observation")}]},
    {"id": "C08", "steps": [
        {"tool": "sql_query", "args": {"q": "select region, sum(amount) from sales group by region"}},
        {"tool": "fs_write", "args": {"path": "reports/c08.md", "content": "<SALES_PLACEHOLDER>"},
         "expect_arg": ("content", "prev_observation")}]},
    {"id": "C09", "steps": [
        {"tool": "sql_query", "args": {"q": "select count(distinct user) from logins"}},
        {"tool": "fs_write", "args": {"path": "reports/c09.md", "content": "<USERS_PLACEHOLDER>"},
         "expect_arg": ("content", "prev_observation")}]},
    {"id": "C10", "steps": [
        {"tool": "sql_query", "args": {"q": "select avg(latency_ms) from requests"}},
        {"tool": "fs_write", "args": {"path": "reports/c10.md", "content": "<AVG2_PLACEHOLDER>"},
         "expect_arg": ("content", "prev_observation")}]},
]

FAMILY_D = [
    {"id": "D01", "steps": [
        {"tool": "http_get", "args": {"url": "http://localhost:8088/status.json"}},
        {"tool": "fs_write", "args": {"path": "out/d01.md", "content": "<BODY_PLACEHOLDER>"},
         "expect_arg": ("content", "prev_observation")}]},
    {"id": "D02", "steps": [
        {"tool": "http_get", "args": {"url": "http://localhost:8088/version"}},
        {"tool": "fs_write", "args": {"path": "out/d02.md", "content": "<VERSION_PLACEHOLDER>"},
         "expect_arg": ("content", "prev_observation")}]},
    {"id": "D03", "steps": [
        {"tool": "http_get", "args": {"url": "http://localhost:8088/summary"}},
        {"tool": "fs_write", "args": {"path": "out/d03.md", "content": "<SUMMARY_PLACEHOLDER>"},
         "expect_arg": ("content", "prev_observation")}]},
    {"id": "D04", "steps": [
        {"tool": "http_get", "args": {"url": "http://localhost:8088/health"}},
        {"tool": "fs_write", "args": {"path": "out/d04.md", "content": "<HEALTH_PLACEHOLDER>"},
         "expect_arg": ("content", "prev_observation")}]},
    {"id": "D05", "steps": [
        {"tool": "http_get", "args": {"url": "http://localhost:8088/counts"}},
        {"tool": "fs_write", "args": {"path": "out/d05.md", "content": "<COUNTS_PLACEHOLDER>"},
         "expect_arg": ("content", "prev_observation")}]},
    {"id": "D06", "steps": [
        {"tool": "http_get", "args": {"url": "http://localhost:8088/status.json"}},
        {"tool": "fs_write", "args": {"path": "out/d06.md", "content": "<S_PLACEHOLDER>"},
         "expect_arg": ("content", "prev_observation")}]},
    {"id": "D07", "steps": [
        {"tool": "http_get", "args": {"url": "http://localhost:8088/version"}},
        {"tool": "fs_write", "args": {"path": "out/d07.md", "content": "<V_PLACEHOLDER>"},
         "expect_arg": ("content", "prev_observation")}]},
    {"id": "D08", "steps": [
        {"tool": "http_get", "args": {"url": "http://localhost:8088/summary"}},
        {"tool": "fs_write", "args": {"path": "out/d08.md", "content": "<SM_PLACEHOLDER>"},
         "expect_arg": ("content", "prev_observation")}]},
    {"id": "D09", "steps": [
        {"tool": "http_get", "args": {"url": "http://localhost:8088/health"}},
        {"tool": "fs_write", "args": {"path": "out/d09.md", "content": "<H_PLACEHOLDER>"},
         "expect_arg": ("content", "prev_observation")}]},
    {"id": "D10", "steps": [
        {"tool": "http_get", "args": {"url": "http://localhost:8088/counts"}},
        {"tool": "fs_write", "args": {"path": "out/d10.md", "content": "<CNT_PLACEHOLDER>"},
         "expect_arg": ("content", "prev_observation")}]},
]

FAMILIES = {"C": FAMILY_C, "D": FAMILY_D}

def get(name: str):
    return FAMILIES[name]

if __name__ == "__main__":
    print(json.dumps({k: len(v) for k, v in FAMILIES.items()}))
