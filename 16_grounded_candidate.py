#!/usr/bin/env python3
"""16_grounded_candidate.py — capture full evidence for every generated candidate.

Record 4 in the journal has validation.reason = "L2a crash: " (empty). This script
re-runs the candidate against its class's _known_correct_for impl and captures
the full stdout/stderr/exit. Verdicts:

  grounded         impl passes AND baseline fails (real discriminator)
  impl_broken      impl exists but crashes on the candidate's test
  baseline_broken  baseline passes (test too weak)
  capability_limit no impl exists for this class -> cannot be graded
"""
import importlib, json, os, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parent
OUTD = ROOT / "state"; OUTD.mkdir(exist_ok=True)
OUT  = OUTD / "candidate_verdicts.jsonl"
ar = importlib.import_module("autonomous_research")

def run(src, test, timeout=5):
    if not src: return None, "", "EMPTY_IMPL"
    code = src.rstrip() + "\n\n" + test
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(code); p = f.name
    try:
        r = subprocess.run([sys.executable, "-I", p], capture_output=True,
                           text=True, timeout=timeout,
                           env={"PATH": os.environ.get("PATH","/usr/bin:/bin")})
        ok = (r.returncode == 0) and ("PASS" in (r.stdout or ""))
        return ok, (r.stdout or "")[-500:], (r.stderr or "")[-1000:]
    except subprocess.TimeoutExpired:
        return False, "", "TIMEOUT"
    finally:
        try: os.unlink(p)
        except OSError: pass

rows = []
for line in (ROOT/"autonomous_journal.jsonl").read_text().splitlines():
    if not line.strip(): continue
    ev = json.loads(line)
    if ev.get("experiment_type") != "generated_test": continue
    cand = ev.get("candidate") or {}
    cls  = (ev.get("gap") or {}).get("class") or ev.get("class")
    impl = ar._known_correct_for(cls, cand)()
    base = ar._baseline_for(cls, cand)()
    test = cand.get("test_ambiguous") or ""
    i_ok, i_out, i_err = run(impl, test)
    b_ok, b_out, b_err = run(base, test)
    if not impl:
        verdict = "capability_limit"
    elif i_ok and not b_ok: verdict = "grounded"
    elif not i_ok and b_ok: verdict = "impl_broken"
    elif not i_ok and not b_ok: verdict = "impl_broken"
    else: verdict = "baseline_broken"
    rows.append({"id": f"C{len(rows)+1:03d}", "class": cls,
                 "template": ev.get("candidate",{}).get("name"),
                 "impl_present": bool(impl),
                 "impl_ok": i_ok, "impl_stderr": i_err.strip().splitlines()[-1][:200] if i_err.strip() else "",
                 "base_ok": b_ok, "verdict": verdict,
                 "timestamp": ev.get("timestamp")})

OUT.write_text("\n".join(json.dumps(r, sort_keys=True) for r in rows) + "\n")
for r in rows:
    print(f"  {r['id']}  {r['class']:<44} {r['verdict']:<20} impl_err={r['impl_stderr'][:60]}")
print(f"\n-> {OUT}")
print(f"\n[HONEST] {sum(1 for r in rows if r['verdict']=='capability_limit')} candidates "
      f"were ungradable because their class has no _known_correct_for impl.")
print("        That is the current generator frontier, stated as evidence.")
