#!/usr/bin/env python3
"""44_claim_both_splits.py — a class is GROUNDED iff it grounds on public AND held-out."""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parent
pub  = [json.loads(l) for l in (ROOT/"state/anchor_verdicts.jsonl").read_text().splitlines() if l.strip()]
held = [json.loads(l) for l in (ROOT/"state/heldout_verdicts.jsonl").read_text().splitlines() if l.strip()]
pub_disc  = {r["class"] for r in pub  if r["verdict"]=="DISCRIMINATES"}
held_disc = {r["class"] for r in held if r["discriminates"]}
both = pub_disc & held_disc
tax  = json.loads((ROOT/"taxonomy.json").read_text())
all_c = {c["name"]+"/"+c["subtype"] for c in tax.get("classes",[])}
print(f"public grounded     : {len(pub_disc)}/{len(all_c)}  {sorted(pub_disc)}")
print(f"held-out grounded   : {len(held_disc)}/{len(all_c)}  {sorted(held_disc)}")
print(f"BOTH (paper claim)  : {len(both)}/{len(all_c)}  {sorted(both)}")
print()
if both == pub_disc:
    print("[OK] every publicly-grounded class also survives the private split.")
    print("     Nothing was overfitting to function names.")
else:
    print("[WARN] classes grounded publicly but NOT on held-out (possible name overfit):")
    for c in sorted(pub_disc - held_disc): print(f"       - {c}")
