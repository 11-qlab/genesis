#!/usr/bin/env python3
"""
Generate 12 (or 20) task families with seed (5 examples) and test (12 items) sets.

Each test item is self-contained: it requires the model to create files,
verify state, then write an answer. Plan shape is scored via
expect_subsequence. Answer correctness is not machine-checked — this
family suite measures PLANNING capability, not answer accuracy.

Usage:
    python3 scripts/build_families.py            # 12 families
    python3 scripts/build_families.py --total 20 # 20 families
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEED_DIR = ROOT / "bench" / "families" / "seed"
TEST_DIR = ROOT / "bench" / "families" / "test"


# ---------------- helpers ----------------

def _w(path: str, content: str) -> dict:
    """One fs_write step in goal text."""
    return {"op": "write", "path": path, "content": content}


def seed_set(items):
    return items


def test_set(items):
    return items


# ---------------- family generators ----------------
# Each generator returns (seed_items, test_items).
# Seed items: 5 examples with a short goal.
# Test items: 12 self-contained tasks with expect_subsequence.

def fam01_consistency():
    """Multi-file consistency: create N files, find the odd one."""
    seed = [
        {"id": "fam1-s01", "goal": "write a.txt='1 2 3', b.txt='4 5 6', c.txt='7 8'. Then read all three and write the name of the file with different word count to answer.txt.",
         "expect_status": "succeeded", "expect_subsequence": ["fs_write", "fs_write", "fs_write", "fs_read", "fs_read", "fs_read", "fs_write"]},
        {"id": "fam1-s02", "goal": "write x.txt='apple', y.txt='banana', z.txt='cherry'. Read all three and write the file with the longest word to answer.txt.",
         "expect_status": "succeeded", "expect_subsequence": ["fs_write", "fs_write", "fs_write", "fs_read", "fs_read", "fs_read", "fs_write"]},
        {"id": "fam1-s03", "goal": "write p.txt='aaa', q.txt='bbb', r.txt='cc'. Read all three, find the shortest, write its name to answer.txt.",
         "expect_status": "succeeded", "expect_subsequence": ["fs_write", "fs_write", "fs_write", "fs_read", "fs_read", "fs_read", "fs_write"]},
        {"id": "fam1-s04", "goal": "create three files with numbers: m1.txt='10', m2.txt='20', m3.txt='5'. Read all three, write the file with the largest number to answer.txt.",
         "expect_status": "succeeded", "expect_subsequence": ["fs_write", "fs_write", "fs_write", "fs_read", "fs_read", "fs_read", "fs_write"]},
        {"id": "fam1-s05", "goal": "write u.txt='red green', v.txt='blue', w.txt='red green'. Read all three, write the pair that matches to answer.txt.",
         "expect_status": "succeeded", "expect_subsequence": ["fs_write", "fs_write", "fs_write", "fs_read", "fs_read", "fs_read", "fs_write"]},
    ]
    tests = []
    patterns = [
        ("alpha.txt", "beta.txt", "gamma.txt", ["1 2 3", "4 5 6", "7 8"], "word count"),
        ("x1.txt", "x2.txt", "x3.txt", ["cat", "dog", "elephant"], "word length"),
        ("v1.txt", "v2.txt", "v3.txt", ["10", "25", "3"], "numeric value"),
        ("m_a.txt", "m_b.txt", "m_c.txt", ["same", "same", "diff"], "content"),
        ("n1.txt", "n2.txt", "n3.txt", ["AA", "AB", "AA"], "content"),
        ("z1.txt", "z2.txt", "z3.txt", ["", "x", "y"], "emptiness"),
        ("k1.txt", "k2.txt", "k3.txt", ["1 2 3 4", "1 2 3", "1 2 3 4"], "word count"),
        ("t1.txt", "t2.txt", "t3.txt", ["TRUE", "FALSE", "TRUE"], "boolean value"),
        ("g1.txt", "g2.txt", "g3.txt", ["red", "green", "blue"], "alphabetical first"),
        ("h1.txt", "h2.txt", "h3.txt", ["5", "10", "15"], "divisibility by 3"),
        ("w1.txt", "w2.txt", "w3.txt", ["hello world", "hello", "hello"], "word count"),
        ("q1.txt", "q2.txt", "q3.txt", ["abc", "abcd", "ab"], "shortest"),
    ]
    for i, (f1, f2, f3, (c1, c2, c3), mode) in enumerate(patterns):
        tests.append({
            "id": f"fam1-{i+1:02d}",
            "goal": (
                f"write {f1}='{c1}', {f2}='{c2}', {f3}='{c3}'. "
                f"Read all three back. By {mode}, exactly one is different from the other two. "
                f"Write its name to answer.txt."
            ),
            "expect_status": "succeeded",
            "expect_subsequence": ["fs_write", "fs_write", "fs_write",
                                    "fs_read", "fs_read", "fs_read", "fs_write"],
        })
    return seed, tests


def fam02_reversal():
    """Cascade reversal: apply operation, then reverse it, verify state."""
    seed = []
    tests = []
    ops = [
        ("s1.txt", "original", "appended", "restore"),
        ("data_a.txt", "line1", "line1\nline2", "revert"),
        ("note.md", "# Title", "# Title\nbody", "undo"),
        ("cfg.txt", "k=v", "k=v\nk2=v2", "reverse"),
        ("rec.json", '{}', '{"k":"v"}', "empty"),
        ("log.txt", "start", "start\nmiddle", "clean"),
        ("memo.txt", "hello", "hello world", "restore"),
        ("draft.md", "draft", "draft\nedit", "revert"),
        ("state.dat", "0", "1", "reset"),
        ("tmp.txt", "keep", "keep extra", "undo"),
        ("raw.txt", "raw", "raw more", "back"),
        ("v1.txt", "v1", "v1 v2", "restore"),
    ]
    for i, (f, orig, new, action) in enumerate(ops):
        tests.append({
            "id": f"fam2-{i+1:02d}",
            "goal": (
                f"write {f}='{orig}'. Then overwrite {f} with '{new}'. "
                f"Then {action} {f} back to its original content. "
                f"Finally read {f} to verify it equals the original."
            ),
            "expect_status": "succeeded",
            "expect_subsequence": ["fs_write", "fs_write", "fs_write", "fs_read"],
        })
    for i in range(5):
        tests_seed = {
            "id": f"fam2-s{i+1:02d}",
            "goal": f"write s{i}.txt='a'. Then overwrite s{i}.txt='ab'. Then overwrite s{i}.txt='a' again. Read it back.",
            "expect_status": "succeeded",
            "expect_subsequence": ["fs_write", "fs_write", "fs_write", "fs_read"],
        }
        seed.append(tests_seed)
    return seed, tests


def fam03_tree():
    """Directory tree reasoning: create nested structure, list and report."""
    seed = [
        {"id": f"fam3-s{i+1:02d}",
         "goal": f"write d{i}/a.txt='1', d{i}/b.txt='2'. Then list d{i} and write the file count to answer{i}.txt.",
         "expect_status": "succeeded",
         "expect_subsequence": ["fs_write", "fs_write", "fs_list", "fs_write"]}
        for i in range(5)
    ]
    tests = []
    specs = [
        ("d1", 2, "file count"),
        ("d2", 3, "file names"),
        ("d3", 4, "file count"),
        ("d4", 2, "largest file"),
        ("d5", 3, "smallest file"),
        ("d6", 1, "file count"),
        ("d7", 4, "file names"),
        ("d8", 2, "file count"),
        ("d9", 3, "alphabetical first"),
        ("d10", 2, "file count"),
        ("d11", 4, "numeric largest"),
        ("d12", 3, "file count"),
    ]
    for i, (d, n, question) in enumerate(specs):
        writes = " ".join([f"write {d}/f{j}.txt='v{j}'." for j in range(n)])
        tests.append({
            "id": f"fam3-{i+1:02d}",
            "goal": f"{writes} Then list {d} and write the {question} to answer.txt.",
            "expect_status": "succeeded",
            "expect_subsequence": ["fs_write"] * n + ["fs_list", "fs_write"],
        })
    return seed, tests


def fam04_join():
    """Cross-file join: match entries across two files."""
    seed = [
        {"id": f"fam4-s{i+1:02d}",
         "goal": f"write id{i}.txt='1\\n2\\n3', name{i}.txt='one\\ntwo\\nthree'. Read both, write '1-one 2-two 3-three' to answer.txt.",
         "expect_status": "succeeded",
         "expect_subsequence": ["fs_write", "fs_write", "fs_read", "fs_read", "fs_write"]}
        for i in range(5)
    ]
    tests = []
    for i in range(12):
        n = 2 + (i % 3)
        ids = "\n".join(str(j) for j in range(n))
        names = "\n".join(["alpha", "beta", "gamma", "delta"][j] for j in range(n))
        tests.append({
            "id": f"fam4-{i+1:02d}",
            "goal": (
                f"write ids_{i}.txt with lines '{ids}'. "
                f"write names_{i}.txt with lines '{names}'. "
                f"Read both, pair by line order, and write each 'id-name' pair on its own line to answer.txt."
            ),
            "expect_status": "succeeded",
            "expect_subsequence": ["fs_write", "fs_write", "fs_read", "fs_read", "fs_write"],
        })
    return seed, tests


def fam05_format_chain():
    """Format conversion: write, transform, transform."""
    seed = [
        {"id": f"fam5-s{i+1:02d}",
         "goal": f"write in{i}.txt='a,b,c'. Read it, write out{i}.txt with each token on its own line. Read out{i} back.",
         "expect_status": "succeeded",
         "expect_subsequence": ["fs_write", "fs_read", "fs_write", "fs_read"]}
        for i in range(5)
    ]
    tests = []
    payloads = [
        "red,green,blue", "1;2;3", "x|y|z", "apple mango pear",
        "A B C D", "one, two, three", "10,20,30", "k1=k2=k3",
        "m,n,o,p", "alpha-beta-gamma", "1.1,2.2,3.3", "q,w,e,r,t",
    ]
    for i, payload in enumerate(payloads):
        tests.append({
            "id": f"fam5-{i+1:02d}",
            "goal": (
                f"write src_{i}.txt='{payload}'. "
                f"Read src_{i}.txt, split on the dominant separator, "
                f"write tokens one per line to mid_{i}.txt. "
                f"Read mid_{i}.txt back."
            ),
            "expect_status": "succeeded",
            "expect_subsequence": ["fs_write", "fs_read", "fs_write", "fs_read"],
        })
    return seed, tests


def fam06_conditional():
    """Conditional branching based on file content."""
    seed = [
        {"id": f"fam6-s{i+1:02d}",
         "goal": f"write cfg{i}.txt='mode=fast'. Read it. If it contains 'fast', write out{i}.txt='quick'; else write 'slow'.",
         "expect_status": "succeeded",
         "expect_subsequence": ["fs_write", "fs_read", "fs_write"]}
        for i in range(5)
    ]
    tests = []
    conditions = [
        ("enabled=true", "yes", "no"), ("enabled=false", "yes", "no"),
        ("count=5", "high", "low"), ("count=1", "high", "low"),
        ("mode=prod", "strict", "lenient"), ("mode=dev", "strict", "lenient"),
        ("level=3", "ok", "fail"), ("level=0", "ok", "fail"),
        ("status=active", "on", "off"), ("status=inactive", "on", "off"),
        ("region=us", "domestic", "foreign"), ("region=eu", "domestic", "foreign"),
    ]
    for i, (content, if_true, if_false) in enumerate(conditions):
        tests.append({
            "id": f"fam6-{i+1:02d}",
            "goal": (
                f"write cfg_{i}.txt='{content}'. Read cfg_{i}.txt. "
                f"If the value on the right of '=' is a truthy-looking positive value, "
                f"write '{if_true}' to result_{i}.txt. Otherwise write '{if_false}'."
            ),
            "expect_status": "succeeded",
            "expect_subsequence": ["fs_write", "fs_read", "fs_write"],
        })
    return seed, tests


def fam07_csv():
    """CSV stats via csv_parse."""
    seed = [
        {"id": f"fam7-s{i+1:02d}",
         "goal": f"write d{i}.csv with header 'name,value' and rows 'a,1' 'b,2' 'c,3'. Parse d{i}.csv, write the mean of value to answer.txt.",
         "expect_status": "succeeded",
         "expect_subsequence": ["fs_write", "csv_parse", "fs_write"]}
        for i in range(5)
    ]
    tests = []
    for i in range(12):
        rows = [("a", i + 1), ("b", i + 3), ("c", i + 5)]
        rows_str = "\\n".join(f"{n},{v}" for n, v in rows)
        tests.append({
            "id": f"fam7-{i+1:02d}",
            "goal": (
                f"write stats_{i}.csv with header 'name,value' and rows: {rows_str}. "
                f"Parse stats_{i}.csv, compute the mean of the 'value' column, write the result to answer.txt."
            ),
            "expect_status": "succeeded",
            "expect_subsequence": ["fs_write", "csv_parse", "fs_write"],
        })
    return seed, tests


def fam08_json():
    """JSON path extraction via json_extract."""
    seed = [
        {"id": f"fam8-s{i+1:02d}",
         "goal": f"write j{i}.json='{{\"k\":\"v{i}\"}}'. Extract key 'k' from j{i}.json and write its value to answer.txt.",
         "expect_status": "succeeded",
         "expect_subsequence": ["fs_write", "json_extract", "fs_write"]}
        for i in range(5)
    ]
    tests = []
    samples = [
        ({"name": "alice", "age": 30}, "name"),
        ({"user": {"id": 42, "email": "a@b"}}, "user.email"),
        ({"items": [10, 20, 30]}, "items[1]"),
        ({"config": {"timeout": 60}}, "config.timeout"),
        ({"tags": ["x", "y", "z"]}, "tags[2]"),
        ({"a": {"b": {"c": "deep"}}}, "a.b.c"),
        ({"count": 100}, "count"),
        ({"list": [{"v": 1}, {"v": 2}]}, "list[1].v"),
        ({"ok": True}, "ok"),
        ({"nested": {"arr": [{"x": "found"}]}}, "nested.arr[0].x"),
        ({"k1": "v1", "k2": "v2"}, "k2"),
        ({"outer": {"inner": "value"}}, "outer.inner"),
    ]
    for i, (obj, path) in enumerate(samples):
        tests.append({
            "id": f"fam8-{i+1:02d}",
            "goal": (
                f"write data_{i}.json with content {json.dumps(obj)}. "
                f"Extract the value at path '{path}' using json_extract, write it to answer.txt."
            ),
            "expect_status": "succeeded",
            "expect_subsequence": ["fs_write", "json_extract", "fs_write"],
        })
    return seed, tests


def fam09_diff():
    """Line diff via text_diff."""
    seed = [
        {"id": f"fam9-s{i+1:02d}",
         "goal": f"write a{i}.txt='x\\ny', b{i}.txt='x\\nz'. Diff them with text_diff, write 'different' to answer.txt.",
         "expect_status": "succeeded",
         "expect_subsequence": ["fs_write", "fs_write", "text_diff", "fs_write"]}
        for i in range(5)
    ]
    tests = []
    pairs = [
        ("a\nb\nc", "a\nb\nc", "identical"),
        ("a\nb\nc", "a\nb", "different"),
        ("1\n2\n3", "1\nx\n3", "different"),
        ("", "", "identical"),
        ("x", "x", "identical"),
        ("same\ndiff\nsame", "same\nsame\nsame", "different"),
        ("a", "b", "different"),
        ("line1\nline2", "line1\nline2", "identical"),
        ("A\nB", "A\nC", "different"),
        ("", "x", "different"),
        ("1\n2\n3\n4", "1\n2\n3\n4", "identical"),
        ("y\nz", "y\nz\nw", "different"),
    ]
    for i, (c1, c2, expected) in enumerate(pairs):
        tests.append({
            "id": f"fam9-{i+1:02d}",
            "goal": (
                f"write f1_{i}.txt='{c1}', f2_{i}.txt='{c2}'. "
                f"Diff them with text_diff, write '{expected}' to answer.txt."
            ),
            "expect_status": "succeeded",
            "expect_subsequence": ["fs_write", "fs_write", "text_diff", "fs_write"],
        })
    return seed, tests


def fam10_regex():
    """Regex search via text_regex."""
    seed = [
        {"id": f"fam10-s{i+1:02d}",
         "goal": f"write text{i}.txt='foo\\nbar\\nbaz'. Search for 'a' with text_regex, write the match count to answer.txt.",
         "expect_status": "succeeded",
         "expect_subsequence": ["fs_write", "text_regex", "fs_write"]}
        for i in range(5)
    ]
    tests = []
    samples = [
        ("alpha\nbeta\ngamma", "a"),
        ("1\n2\n3\n4\n5", "[0-9]"),
        ("hello\nworld", "o"),
        ("abc\nabd\nabe", "ab[c-e]"),
        ("test\nTEST\nTest", "TEST"),
        ("x=1\ny=2\nz=3", "="),
        ("no matches here", "xyz"),
        ("a\nab\nabc", "^a"),
        ("end$\nnot", "end"),
        ("123-456\n789", "[0-9]{3}"),
        ("", "."),
        ("word word word", "word"),
    ]
    for i, (text, pattern) in enumerate(samples):
        tests.append({
            "id": f"fam10-{i+1:02d}",
            "goal": (
                f"write src_{i}.txt='{text}'. "
                f"Search src_{i}.txt for regex '{pattern}' using text_regex, "
                f"write the number of matching lines to answer.txt."
            ),
            "expect_status": "succeeded",
            "expect_subsequence": ["fs_write", "text_regex", "fs_write"],
        })
    return seed, tests


def fam11_sql():
    """SQL query via sqlite_query."""
    seed = [
        {"id": f"fam11-s{i+1:02d}",
         "goal": f"run sqlite_query on 'db{i}.sqlite3' with 'SELECT 1 AS x'. Write the result to answer.txt.",
         "expect_status": "succeeded",
         "expect_subsequence": ["sqlite_query", "fs_write"]}
        for i in range(5)
    ]
    # NOTE: sqlite_query needs an existing DB. We make the goal "query the db, write result"
    # and expect the model to attempt it. If the db doesn't exist, the tool returns an error
    # and status != succeeded. That's a valid negative.
    tests = []
    queries = [
        "SELECT 1 AS x",
        "SELECT 42 AS answer",
        "SELECT 'hello' AS greeting",
        "SELECT 1+2 AS sum",
        "SELECT COUNT(*) AS c FROM sqlite_master",
        "SELECT 100 AS n",
        "SELECT 'x' AS col",
        "SELECT NULL AS n",
        "SELECT 3.14 AS pi",
        "SELECT 'abc' AS s",
        "SELECT 7*6 AS product",
        "SELECT 'done' AS status",
    ]
    for i, sql in enumerate(queries):
        tests.append({
            "id": f"fam11-{i+1:02d}",
            "goal": (
                f"run sqlite_query against db_{i}.sqlite3 with the SQL '{sql}'. "
                f"Write the resulting rows to answer.txt."
            ),
            "expect_status": "succeeded",
            "expect_subsequence": ["sqlite_query", "fs_write"],
        })
    return seed, tests


def fam12_hash():
    """SHA-256 verification via hash_check."""
    seed = [
        {"id": f"fam12-s{i+1:02d}",
         "goal": f"write h{i}.txt='hello'. Compute its sha256 manually is not required — call hash_check on h{i}.txt with the sha256 of 'hello'. Write 'match' or 'mismatch' to answer.txt.",
         "expect_status": "succeeded",
         "expect_subsequence": ["fs_write", "hash_check", "fs_write"]}
        for i in range(5)
    ]
    # sha256("hello") = 2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824
    tests = []
    for i in range(12):
        content = f"data_{i}"
        expected_wrong = "0" * 64
        tests.append({
            "id": f"fam12-{i+1:02d}",
            "goal": (
                f"write v_{i}.txt='{content}'. Run hash_check on v_{i}.txt with expected digest '{expected_wrong}'. "
                f"Report 'match' or 'mismatch' in answer.txt."
            ),
            "expect_status": "succeeded",
            "expect_subsequence": ["fs_write", "hash_check", "fs_write"],
        })
    return seed, tests


# ---------------- family registry ----------------

FAMILIES = {
    "fam01": fam01_consistency,
    "fam02": fam02_reversal,
    "fam03": fam03_tree,
    "fam04": fam04_join,
    "fam05": fam05_format_chain,
    "fam06": fam06_conditional,
    "fam07": fam07_csv,
    "fam08": fam08_json,
    "fam09": fam09_diff,
    "fam10": fam10_regex,
    "fam11": fam11_sql,
    "fam12": fam12_hash,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--total", type=int, default=12,
                    help="How many families to write (12 default; 20 to extend)")
    args = ap.parse_args()

    SEED_DIR.mkdir(parents=True, exist_ok=True)
    TEST_DIR.mkdir(parents=True, exist_ok=True)

    written = 0
    for name, gen in FAMILIES.items():
        if written >= args.total:
            break
        seed, test = gen()
        seed_path = SEED_DIR / f"{name}.jsonl"
        test_path = TEST_DIR / f"{name}.jsonl"
        with seed_path.open("w") as f:
            for it in seed:
                f.write(json.dumps(it) + "\n")
        with test_path.open("w") as f:
            for it in test:
                f.write(json.dumps(it) + "\n")
        print(f"  {name}: seed={len(seed)} test={len(test)}")
        written += 1

    print(f"\nwrote {written} families x (5 seed + 12 test) = {written * 17} items")


if __name__ == "__main__":
    main()
