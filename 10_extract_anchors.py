#!/usr/bin/env python3
"""10_extract_anchors.py — freeze the anchor spec from source code.

Reads TEMPLATES, _known_correct_for, _baseline_for from autonomous_research.
Writes bench/anchors/v1.jsonl  (deterministic spec, hashable).
Nothing here executes anything — pure extraction. Hash goes to v1.sha256.
"""
import hashlib, importlib, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUTD = ROOT / "bench/anchors"; OUTD.mkdir(parents=True, exist_ok=True)
OUT  = OUTD / "v1.jsonl"
HASH = OUTD / "v1.sha256"

def die(m): print(f"EXTRACT_REFUSED: {m}", file=sys.stderr); sys.exit(2)

try:
    ar = importlib.import_module("autonomous_research")
except Exception as e:
    die(f"cannot import autonomous_research: {e}")

for n in ("TEMPLATES", "_known_correct_for", "_baseline_for"):
    if not hasattr(ar, n): die(f"autonomous_research.{n} missing")

try:
    ar.load_approved_templates()   # merge staged_tests if any
except Exception as e:
    print(f"[warn] load_approved_templates failed: {e}", file=sys.stderr)

rows, skipped = [], []
for cls, tpls in ar.TEMPLATES.items():
    for tpl in tpls:
        try:
            impl_src = ar._known_correct_for(cls, tpl)()
            base_src = ar._baseline_for(cls, tpl)()
        except Exception as e:
            skipped.append({"class": cls, "template": tpl.get("name"), "reason": f"extract: {e!r}"})
            continue
        if not impl_src:
            skipped.append({"class": cls, "template": tpl.get("name"), "reason": "no known_correct impl"})
            continue
        variants = [v for v in ("test_ambiguous","test_recipe") if tpl.get(v)]
        if not variants and tpl.get("test"):
            variants = ["test"]
        if not variants:
            skipped.append({"class": cls, "template": tpl.get("name"),
                            "reason": "no test_* or test field"})
            continue
        for variant in variants:
            test_src = tpl.get(variant) if variant != "test" else tpl["test"]
            rows.append({
                "id": f"A{len(rows)+1:03d}",
                "class": cls,
                "template": tpl.get("name", "unnamed"),
                "variant": variant,
                "impl_src": impl_src,
                "base_src": base_src,
                "test_src": test_src,
            })

if not rows:
    die("no anchors extracted — TEMPLATES may be empty or all known_correct missing")

OUT.write_text("\n".join(json.dumps(r, sort_keys=True) for r in rows) + "\n")
HASH.write_text(hashlib.sha256(OUT.read_bytes()).hexdigest() + "\n")

print(f"extracted {len(rows)} anchors  -> {OUT}")
print(f"sha256    {HASH.read_text().strip()[:16]}…  -> {HASH}")
if skipped:
    print(f"\nskipped {len(skipped)} (reasons):")
    for s in skipped: print(f"  {s}")
print(f"\n[ OK ] next: ./20_verify_anchors.py")
