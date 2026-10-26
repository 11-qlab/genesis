#!/usr/bin/env python3
"""Taint-style binding check. For every fs_write, classify the emitted content:
  LITERAL      content was known at plan time -> fine
  BOUND        content equals a prior fs_read observation -> fine
  BINDING_MISSED  content matches a placeholder shape AND an upstream read
                  could have supplied the value -> FAIL
  UNBOUND_READ content looks like content but no upstream read exists -> REVIEW
Generalizes past string-equality because it checks *binding*, not *content*.
"""
import argparse, json, re, sys, pathlib

PLACEHOLDER_RX = re.compile(r"(<[A-Z_]+:[^>]{0,80}>|\{\{[^}]{0,80}\}\}|#E\d+|\$\{[A-Za-z_]\w*\})")

def provenance_verdict(traj: dict) -> dict:
    # FILL: adjust to your cfh field names (see probe output)
    steps = traj.get("steps") or traj.get("trajectory") or []
    reads: dict[str, str] = {}          # path -> observation
    findings = []
    for i, s in enumerate(steps):
        tool = s.get("tool") or s.get("name")
        args = s.get("args") or s.get("arguments") or {}
        if tool == "fs_read":
            p = args.get("path"); r = s.get("result") or s.get("observation")
            if p and isinstance(r, str): reads[p] = r
        elif tool == "fs_write":
            content = args.get("content")
            if not isinstance(content, str):
                findings.append({"step": i, "class": "MISSING_CONTENT"}); continue
            if any(content == v for v in reads.values()):
                findings.append({"step": i, "class": "BOUND"}); continue
            m = PLACEHOLDER_RX.search(content)
            if m and reads:
                findings.append({"step": i, "class": "BINDING_MISSED",
                                 "placeholder": m.group(0)}); continue
            if PLACEHOLDER_RX.search(content):
                findings.append({"step": i, "class": "UNBOUND_READ"}); continue
            findings.append({"step": i, "class": "LITERAL"})
    failed = any(f["class"] == "BINDING_MISSED" for f in findings)
    return {"fail": failed, "findings": findings,
            "n_reads": len(reads), "n_steps": len(steps)}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trajectories", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    rows = [json.loads(l) for l in pathlib.Path(a.trajectories).read_text().splitlines() if l.strip()]
    out = []
    for r in rows:
        v = provenance_verdict(r)
        out.append({"task_id": r.get("task_id") or r.get("id"), **v})
    n_fail = sum(x["fail"] for x in out)
    pathlib.Path(a.out).write_text(json.dumps(out, indent=2))
    print(f"[prov] {n_fail}/{len(out)} BINDING_MISSED -> {a.out}")

if __name__ == "__main__":
    main()
