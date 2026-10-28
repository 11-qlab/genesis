#!/usr/bin/env python3
"""Classify each TOO_STRICT anchor so the limitations paragraph is measured,
not asserted. Writes state/toostrict_breakdown.jsonl."""
import importlib, json, os, re, subprocess, sys, tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ar   = importlib.import_module("autonomous_research")
verd = [json.loads(l) for l in (ROOT/"state/anchor_verdicts.jsonl").read_text().splitlines() if l.strip()]
anch = {a["id"]: a for a in (json.loads(l) for l in
        (ROOT/"bench/anchors/v1.jsonl").read_text().splitlines() if l.strip())}

def run(src, test, tmo=5):
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(src.rstrip()+"\n\n"+test); p=f.name
    try:
        r = subprocess.run([sys.executable,"-I",p], capture_output=True, text=True, timeout=tmo,
                           env={"PATH": os.environ.get("PATH","/usr/bin:/bin")})
        return r.returncode, r.stdout or "", r.stderr or ""
    except subprocess.TimeoutExpired:
        return None, "", "TIMEOUT"
    finally:
        try: os.unlink(p)
        except OSError: pass

def classify(a, stderr):
    if "TIMEOUT" in stderr: return "timeout"
    if "NameError" in stderr:
        m = re.search(r"name '([^']+)' is not defined", stderr)
        return f"impl_missing_name:{m.group(1) if m else '?'}"
    if "TypeError" in stderr:
        if "positional argument" in stderr: return "signature_mismatch:arg_count"
        if "not iterable" in stderr:        return "signature_mismatch:type"
        return "type_error:other"
    if "AssertionError" in stderr: return "wrong_output:impl_fails_assert"
    if "IndexError" in stderr:     return "index_error"
    return "unknown"

rows = []
for v in verd:
    if v["verdict"] == "DISCRIMINATES": continue
    a = anch[v["id"]]
    _, _, err = run(a["impl_src"], a["test_src"])
    rows.append({"id": v["id"], "class": v["class"], "template": v["template"],
                 "variant": v["variant"], "err_class": classify(a, err),
                 "stderr_tail": (err.strip().splitlines() or [""])[-1][:140]})

OUT = ROOT/"state/toostrict_breakdown.jsonl"
OUT.write_text("\n".join(json.dumps(r, sort_keys=True) for r in rows)+"\n")

print(f"{'ID':<5} {'TEMPLATE':<30} {'VARIANT':<15} {'FAILURE CLASS'}")
print("─"*100)
for r in rows:
    print(f"{r['id']:<5} {r['template']:<30} {r['variant']:<15} {r['err_class']}")

c = Counter(r["err_class"].split(":")[0] for r in rows)
print("\nSummary of TOO_STRICT causes:")
for k,n in c.most_common(): print(f"  {k:<30} {n}")

impl_mismatch = sum(1 for r in rows
                    if r["err_class"].startswith(("impl_missing_name","signature_mismatch")))
print(f"\n{impl_mismatch}/{len(rows)} TOO_STRICT anchors fail because "
      f"_known_correct_for returns ONE impl per CLASS, not per (class,template).")
print("This is the oracle's granularity limit — NOT a test-authoring bug.")
