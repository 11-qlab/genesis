#!/usr/bin/env python3
"""Rewrite 10_extract_anchors.py so it falls back from test_ambiguous/test_recipe
to a single `test` field. Emits variant label 'test' in that case."""
from pathlib import Path
p = Path(__file__).resolve().parent / "10_extract_anchors.py"
src = p.read_text()
old = '''        for variant in ("test_ambiguous", "test_recipe"):
            test_src = tpl.get(variant)
            if not test_src:
                skipped.append({"class": cls, "template": tpl.get("name"),
                                "variant": variant, "reason": "variant absent"})
                continue'''
new = '''        variants = [v for v in ("test_ambiguous","test_recipe") if tpl.get(v)]
        if not variants and tpl.get("test"):
            variants = ["test"]
        if not variants:
            skipped.append({"class": cls, "template": tpl.get("name"),
                            "reason": "no test_* or test field"})
            continue
        for variant in variants:
            test_src = tpl.get(variant) if variant != "test" else tpl["test"]'''
assert old in src, "anchor text not found — 10_ was edited; patch aborted"
p.write_text(src.replace(old, new))
print("patched 10_extract_anchors.py: fallback to single `test` field")
