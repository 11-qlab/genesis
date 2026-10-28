#!/usr/bin/env python3
"""Patch: 40_ conflates cross-family (model evidence) with grounded (anchor verified).
Rewrite the summary line so the paper uses the weaker true claim."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent
tax = json.loads((ROOT/"taxonomy.json").read_text())
verd = [json.loads(l) for l in (ROOT/"state/anchor_verdicts.jsonl").read_text().splitlines() if l.strip()]
from collections import Counter
grounded = {v["class"] for v in verd if v["verdict"]=="DISCRIMINATES"}
all_cls = {c["name"]+"/"+c["subtype"] for c in tax.get("classes",[])}
cross_family = {c["name"]+"/"+c["subtype"] for c in tax.get("classes",[])
                if len(c.get("evidence",{}).get("affected_models",{})) >= 2}
print(f"classes total       : {len(all_cls)}")
print(f"cross-family (model): {len(cross_family)}/{len(all_cls)}  {sorted(cross_family)}")
print(f"grounded (exec)     : {len(grounded)}/{len(all_cls)}  {sorted(grounded)}")
print()
print("PAPER HEADLINE must use 'grounded' — the anchor-verified subset.")
