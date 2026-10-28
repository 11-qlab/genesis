#!/usr/bin/env python3
"""Probe: for every template, run known-correct vs baseline against its test body.
Tell us BEFORE re-extracting whether each class can ground, and why not."""
import importlib, json, os, subprocess, sys, tempfile
ar = importlib.import_module("autonomous_research")

def run(src, test, tmo=5):
    code = src.rstrip() + "\n\n" + test
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(code); p = f.name
    try:
        r = subprocess.run([sys.executable, "-I", p], capture_output=True, text=True, timeout=tmo,
                           env={"PATH": os.environ.get("PATH","/usr/bin:/bin")})
        return r.returncode == 0 and "PASS" in (r.stdout or ""), (r.stderr or "").strip().splitlines()[-1][:90] if r.stderr else ""
    except subprocess.TimeoutExpired:
        return False, "TIMEOUT"
    finally:
        try: os.unlink(p)
        except OSError: pass

for cls, tpls in ar.TEMPLATES.items():
    print(f"\n### {cls}")
    impl = ar._known_correct_for(cls, {})()
    for t in tpls:
        name = t.get("name")
        test = t.get("test") or t.get("test_ambiguous")
        if not test:
            print(f"  {name:<30} NO TEST BODY"); continue
        base = ar._baseline_for(cls, t)()
        i_ok, i_e = run(impl, test); b_ok, b_e = run(base, test)
        verdict = ("DISCRIMINATES" if i_ok and not b_ok else
                   "TOO_WEAK" if i_ok and b_ok else
                   "TOO_STRICT")
        print(f"  {name:<30} impl={'OK' if i_ok else 'FAIL':<4} base={'OK' if b_ok else 'FAIL':<4} -> {verdict}")
        if not i_ok: print(f"      impl err: {i_e}")
        if verdict == "TOO_STRICT" and "NameError" in i_e:
            # name mismatch check
            import re
            calls = re.findall(r'\b([a-z_][a-z0-9_]*)\s*\(', test)
            print(f"      test calls: {sorted(set(calls))[:6]}")
