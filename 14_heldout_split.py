#!/usr/bin/env python3
"""14_heldout_split.py — produce a private held-out variant of every anchor.

Mutation: rename every function defined or called in impl/test consistently.
The generator only ever sees bench/anchors/v1.jsonl (public). The verifier runs
both v1 and v1_heldout. A class is grounded iff it grounds on BOTH.

Why: prevents a candidate overfitting to surface features (e.g., the literal
name 'binary_search') from passing. It has to work on an unseen name too.
"""
import hashlib, json, re, os, subprocess, sys, tempfile
from pathlib import Path
ROOT   = Path(__file__).resolve().parent
PUBLIC = ROOT / "bench/anchors/v1.jsonl"
HELD   = ROOT / "bench/anchors/v1_heldout.jsonl"
HASH   = ROOT / "bench/anchors/v1_heldout.sha256"
OUTD   = ROOT / "state"; OUTD.mkdir(exist_ok=True)
VERD   = OUTD / "heldout_verdicts.jsonl"

def rename(src, mapping):
    for old, new in mapping.items():
        src = re.sub(rf'\b{re.escape(old)}\b', new, src)
    return src

def build_mapping(impl, test):
    names = set(re.findall(r'\bdef\s+([A-Za-z_]\w*)', impl))
    names |= set(re.findall(r'\b([A-Za-z_]\w*)\s*\(', test))
    builtins = {"print","len","range","sorted","max","min","abs","int","str","list","set","dict"}
    return {n: n + "_ho" for n in names if n not in builtins and not n.startswith("_")}

def run(src, test, tmo=5):
    if not src: return None
    code = src.rstrip() + "\n\n" + test
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(code); p = f.name
    try:
        r = subprocess.run([sys.executable, "-I", p], capture_output=True,
                           text=True, timeout=tmo,
                           env={"PATH": os.environ.get("PATH","/usr/bin:/bin")})
        return (r.returncode == 0) and ("PASS" in (r.stdout or ""))
    except subprocess.TimeoutExpired:
        return False
    finally:
        try: os.unlink(p)
        except OSError: pass

anchors = [json.loads(l) for l in PUBLIC.read_text().splitlines() if l.strip()]
held, verd = [], []
for a in anchors:
    m = build_mapping(a["impl_src"], a["test_src"])
    h_impl = rename(a["impl_src"], m)
    h_base = rename(a["base_src"], m)
    h_test = rename(a["test_src"], m)
    h = {**a, "id": a["id"] + "H", "impl_src": h_impl, "base_src": h_base, "test_src": h_test,
         "renamed": sorted(m.keys())}
    held.append(h)
    i_ok, b_ok = run(h_impl, h_test), run(h_base, h_test)
    verd.append({"id": h["id"], "class": h["class"],
                 "impl_ok": i_ok, "base_ok": b_ok,
                 "discriminates": bool(i_ok and not b_ok),
                 "renamed": sorted(m.keys())})

HELD.write_text("\n".join(json.dumps(h, sort_keys=True) for h in held) + "\n")
HASH.write_text(hashlib.sha256(HELD.read_bytes()).hexdigest() + "\n")
VERD.write_text("\n".join(json.dumps(v, sort_keys=True) for v in verd) + "\n")

passed = sum(v["discriminates"] for v in verd)
print(f"held-out anchors : {len(held)}   sha256 {HASH.read_text().strip()[:16]}")
print(f"discriminating   : {passed}/{len(held)}")
for v in verd:
    mark = "✓" if v["discriminates"] else "✗"
    print(f"  {mark} {v['id']:<6} {v['class']:<44} renamed={v['renamed'][:3]}")
print(f"\n-> {HELD}\n-> {VERD}")
print("\nGenerator NEVER reads v1_heldout.jsonl. Only 20_/21_ (verifier) does.")
print(f"[ OK ] next: patch 42_claims.py to require BOTH public and held-out grounded.")
