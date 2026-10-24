#!/usr/bin/env python3
"""
Generate fam13 (path ambiguity) and fam14 (hull boundary) benches.

fam13 — same goal achievable via multiple tool paths. Scoring subsequence
        is ["fs_read"] (common tail). Which path the model chose is
        analyzed post-hoc by run_path_ambiguity.py from tool_sequence.

fam14 — two matched sub-benches with identical structure:
        fam14in  — fs_read on known content  (inside hull)
        fam14out — text_regex on files       (outside hull)
        Same 3-step plan shape. Accuracy gap = hull effect.
"""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEED_DIR = ROOT / "bench" / "families" / "seed"
TEST_DIR = ROOT / "bench" / "families" / "test"


def build_fam13():
    seed = []
    for i in range(5):
        seed.append({
            "id": f"fam13-s{i+1:02d}",
            "goal": (
                f"ensure f{i}.txt exists with content 'hello{i}', then read it back. "
                f"Two valid paths: (A) fs_write then fs_read, or "
                f"(B) fs_list, then fs_write, then fs_read. Use whichever you prefer."
            ),
            "expect_status": "succeeded",
            "expect_subsequence": ["fs_read"],
            "expect_tool": None,
        })

    payloads = [
        ("cfg.txt", "value=42"), ("note.md", "# title"),
        ("data.csv", "a,b,c"), ("log.txt", "start"),
        ("state.json", '{"ok": true}'), ("config.ini", "k=v"),
        ("memo.txt", "remember this"), ("draft.txt", "first draft"),
        ("index.txt", "0"), ("raw.bin", "binaryish"),
        ("tmp.txt", "temporary"), ("final.txt", "done"),
    ]
    tests = []
    for i, (fname, content) in enumerate(payloads):
        tests.append({
            "id": f"fam13-{i+1:02d}",
            "goal": (
                f"ensure {fname} exists with content '{content}', then read it back. "
                f"Two valid paths: (A) fs_write then fs_read, or "
                f"(B) fs_list, then fs_write, then fs_read."
            ),
            "expect_status": "succeeded",
            "expect_subsequence": ["fs_read"],
            "expect_tool": None,
        })
    return seed, tests


def build_fam14():
    seed_in = []
    for i in range(5):
        seed_in.append({
            "id": f"fam14in-s{i+1:02d}",
            "goal": (
                f"write in{i}.txt='alpha{i}'. read in{i}.txt with fs_read. "
                f"write its contents to answer.txt."
            ),
            "expect_status": "succeeded",
            "expect_subsequence": ["fs_write", "fs_read", "fs_write"],
            "expect_tool": None,
        })

    seed_out = []
    for i in range(5):
        seed_out.append({
            "id": f"fam14out-s{i+1:02d}",
            "goal": (
                f"write src{i}.txt='needle-{i}'. search src{i}.txt for 'needle' "
                f"with text_regex. write the match count to answer.txt."
            ),
            "expect_status": "succeeded",
            "expect_subsequence": ["fs_write", "text_regex", "fs_write"],
            "expect_tool": None,
        })

    in_payloads = [
        ("a.txt", "value_a"), ("b.txt", "value_b"), ("c.txt", "value_c"),
        ("d.txt", "value_d"), ("e.txt", "value_e"), ("f.txt", "value_f"),
        ("g.txt", "value_g"), ("h.txt", "value_h"), ("i.txt", "value_i"),
        ("j.txt", "value_j"), ("k.txt", "value_k"), ("l.txt", "value_l"),
    ]
    tests_in = []
    for i, (fname, content) in enumerate(in_payloads):
        tests_in.append({
            "id": f"fam14in-{i+1:02d}",
            "goal": (
                f"write {fname}='{content}', read it back with fs_read, "
                f"write its contents to answer.txt."
            ),
            "expect_status": "succeeded",
            "expect_subsequence": ["fs_write", "fs_read", "fs_write"],
            "expect_tool": None,
        })

    out_payloads = [
        ("t1.txt", "red apple\\ngreen apple\\nblue sky", "apple"),
        ("t2.txt", "1 2 3\\n4 5 6\\n7 8 9", "[0-9]+"),
        ("t3.txt", "a=1\\nb=2\\nc=3", "="),
        ("t4.txt", "hello world", "world"),
        ("t5.txt", "x\\nx\\nx\\nx", "x"),
        ("t6.txt", "abc\\ndef", "def"),
        ("t7.txt", "test one\\ntest two", "test"),
        ("t8.txt", "line_a\\nline_b\\nline_c", "line_"),
        ("t9.txt", "no matches here", "zzz"),
        ("t10.txt", "end1\\nend2", "end"),
        ("t11.txt", "AAA\\nAAB\\nAAC", "AAA"),
        ("t12.txt", "1-2-3", "[0-9]"),
    ]
    tests_out = []
    for i, (fname, content, pattern) in enumerate(out_payloads):
        tests_out.append({
            "id": f"fam14out-{i+1:02d}",
            "goal": (
                f"write {fname}='{content}', then use text_regex to search "
                f"it for pattern '{pattern}', then write the match count "
                f"to answer.txt."
            ),
            "expect_status": "succeeded",
            "expect_subsequence": ["fs_write", "text_regex", "fs_write"],
            "expect_tool": None,
        })
    return (seed_in, seed_out), (tests_in, tests_out)


def main():
    SEED_DIR.mkdir(parents=True, exist_ok=True)
    TEST_DIR.mkdir(parents=True, exist_ok=True)

    s13, t13 = build_fam13()
    (SEED_DIR / "fam13.jsonl").write_text("\n".join(json.dumps(it) for it in s13) + "\n")
    (TEST_DIR / "fam13.jsonl").write_text("\n".join(json.dumps(it) for it in t13) + "\n")
    print(f"  fam13: seed={len(s13)} test={len(t13)}")

    (s_in, s_out), (t_in, t_out) = build_fam14()
    (SEED_DIR / "fam14in.jsonl").write_text("\n".join(json.dumps(it) for it in s_in) + "\n")
    (SEED_DIR / "fam14out.jsonl").write_text("\n".join(json.dumps(it) for it in s_out) + "\n")
    (TEST_DIR / "fam14in.jsonl").write_text("\n".join(json.dumps(it) for it in t_in) + "\n")
    (TEST_DIR / "fam14out.jsonl").write_text("\n".join(json.dumps(it) for it in t_out) + "\n")
    print(f"  fam14in:  seed={len(s_in)} test={len(t_in)}")
    print(f"  fam14out: seed={len(s_out)} test={len(t_out)}")
    print(f"\nwrote 3 new families")


if __name__ == "__main__":
    main()
