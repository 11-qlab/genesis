#!/usr/bin/env python3
"""20_verify_anchors.py — execute the ground-truth oracle.

For each frozen anchor:
  known_correct impl  + test  -> MUST exit 0 AND print 'PASS'
  baseline stub       + test  -> MUST exit non-zero (assertion fires)

If both hold, the test is a valid discriminator (DISCRIMINATES).
Otherwise: too strict (impl fails) or too weak (base passes).

This is the in-loop, execution-verifiable oracle the 2026 survey says nobody has.
Writes state/anchor_verdicts.jsonl. Exit 1 if any class lacks a valid discriminator.

Sandbox: subprocess.run(-I), stripped env, 5s timeout, tmpfile. Stops accidents.
Not adversarial-hardened. Known limitation.
"""
import hashlib, json, os, subprocess, sys, tempfile
from collections import defaultdict
from pathlib import Path

ROOT   = Path(__file__).resolve().parent
ANCHOR = ROOT / "bench/anchors/v1.jsonl"
HASH   = ROOT / "bench/anchors/v1.sha256"
OUTD   = ROOT / "state"; OUTD.mkdir(exist_ok=True)
VERD   = OUTD / "anchor_verdicts.jsonl"

def die(m): print(f"VERIFY_REFUSED: {m}", file=sys.stderr); sys.exit(3)

if not ANCHOR.exists(): die(f"missing {ANCHOR} — run ./10_extract_anchors.py")
if not HASH.exists():   die(f"missing {HASH}")
want = HASH.read_text().strip()
got  = hashlib.sha256(ANCHOR.read_bytes()).hexdigest()
if got != want: die(f"anchor hash mismatch (want {want[:16]} got {got[:16]}) — anchor mutated")

anchors = [json.loads(l) for l in ANCHOR.read_text().splitlines() if l.strip()]
if not anchors: die("anchor file empty")

def run_one(src: str, test: str, timeout=5):
    """Return (ok:bool, note:str). ok means exit 0 AND 'PASS' in stdout."""
    code = src.rstrip() + "\n\n" + test
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(code); path = f.name
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"),
           "PYTHONDONTWRITEBYTECODE": "1"}
    try:
        p = subprocess.run([sys.executable, "-I", path],
                           capture_output=True, text=True, timeout=timeout, env=env)
        stdout, stderr = (p.stdout or ""), (p.stderr or "")
        ok = (p.returncode == 0) and ("PASS" in stdout)
        if ok:                     note = "PASS"
        elif p.returncode != 0:    note = "exit:" + str(p.returncode) + ":" + stderr.strip().splitlines()[-1][:100] if stderr.strip() else "exit:"+str(p.returncode)
        else:                      note = "exit0-no-PASS (template missing print('PASS')?)"
        return ok, note
    except subprocess.TimeoutExpired:
        return False, "TIMEOUT"
    finally:
        try: os.unlink(path)
        except OSError: pass

rows = []
by_class = defaultdict(lambda: {"discriminates": 0, "total": 0, "fails": []})
for a in anchors:
    impl_ok, impl_note = run_one(a["impl_src"], a["test_src"])
    base_ok, base_note = run_one(a["base_src"], a["test_src"])
    discriminates = impl_ok and not base_ok
    if impl_ok and base_ok:   verdict = "TOO_WEAK (baseline passes)"
    elif not impl_ok:         verdict = "TOO_STRICT (known-correct fails)"
    else:                     verdict = "DISCRIMINATES"
    rows.append({**{k: a[k] for k in ("id","class","template","variant")},
                 "impl_ok": impl_ok, "impl_note": impl_note,
                 "base_ok": base_ok, "base_note": base_note,
                 "verdict": verdict})
    g = by_class[a["class"]]
    g["total"] += 1
    if discriminates: g["discriminates"] += 1
    else: g["fails"].append({"id": a["id"], "variant": a["variant"], "verdict": verdict,
                              "impl_note": impl_note, "base_note": base_note})

with VERD.open("w") as f:
    for r in rows: f.write(json.dumps(r, sort_keys=True) + "\n")

print(f"{'ID':<5} {'CLASS':<44} {'VARIANT':<16} {'VERDICT'}")
print("─" * 100)
for r in rows:
    print(f"{r['id']:<5} {r['class']:<44} {r['variant']:<16} {r['verdict']}")

print("\nPer-class summary:")
n_grounded, n_ungrounded = 0, []
for cls, s in sorted(by_class.items()):
    ok = s["discriminates"] > 0
    n_grounded += ok
    if not ok: n_ungrounded.append(cls)
    mark = "✓" if ok else "✗"
    print(f"  {mark} {cls:<44} {s['discriminates']}/{s['total']} anchors discriminate")

print(f"\nclasses grounded: {n_grounded}/{len(by_class)}")
if n_ungrounded:
    print("classes WITHOUT any valid discriminator:")
    for c in n_ungrounded: print(f"  - {c}")
    sys.exit(1)
print("[ OK ] all classes grounded — ground truth verified. Next: ./30_anomaly_report.py")
