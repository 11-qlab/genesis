#!/usr/bin/env python3
"""Taint-style binding check against persisted trace format.

Schema: each row has plan_raw (nested JSON) and content (emitted write content).
Reads the plan's fs_write.args.content and classifies it.
"""
import argparse, json, pathlib, re, sys
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from verifier_deterministic import TEMPLATE_RE

def classify(row):
    try: plan = json.loads(row.get("plan_raw") or "{}")
    except Exception: plan = {}
    steps = plan.get("steps", [])
    reads = [s for s in steps if s.get("tool") == "fs_read"]
    writes = [s for s in steps if s.get("tool") == "fs_write"]
    if not writes:
        return {"class": "no_write", "fail": True}
    content = (writes[0].get("args") or {}).get("content")
    if content is None:
        return {"class": "no_content", "fail": True}
    is_ph = bool(TEMPLATE_RE.search(content))
    expected = row.get("expected")
    wrong = expected is not None and not is_ph and content != expected
    return {
        "class": "placeholder" if is_ph else ("wrong_literal" if wrong else "ok"),
        "content": content, "expected": expected,
        "reads": len(reads), "writes": len(writes),
        "fail": is_ph or wrong
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trajectories", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    rows = [json.loads(l) for l in pathlib.Path(a.trajectories).read_text().splitlines() if l.strip()]
    out = []
    for r in rows:
        c = classify(r)
        out.append({"item": r.get("item"), "cond": r.get("cond"), **c})
    n_fail = sum(x["fail"] for x in out)
    pathlib.Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(a.out).write_text(json.dumps(out, indent=2))
    print(f"[prov] {n_fail}/{len(out)} fail -> {a.out}")

if __name__ == "__main__":
    main()
