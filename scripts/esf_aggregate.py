#!/usr/bin/env python3
"""Aggregate esf_run_absolute.py output into a L1-L4 sensitivity/specificity table."""
import argparse, json, sys
from pathlib import Path
from collections import defaultdict

LEVELS = ["L1", "L2", "L3", "L4"]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verdicts", required=True)
    ap.add_argument("--traj-dir", required=True, help="dir containing original traj JSONs with label field")
    ap.add_argument("--out", default="esf_curve.json")
    args = ap.parse_args()

    verdicts = json.loads(Path(args.verdicts).read_text())
    # load labels: traj stem -> label
    labels = {}
    for p in Path(args.traj_dir).glob("*.json"):
        try:
            d = json.loads(p.read_text())
            labels[p.stem] = d.get("label") or d.get("mutation_type") or "correct"
        except Exception:
            pass

    agg = defaultdict(lambda: {"correct_total": 0, "correct_flag": 0,
                               "mut_total": 0, "mut_flag": 0})
    for r in verdicts:
        key = r["level"]
        lab = labels.get(r["traj"], "correct")
        if lab == "correct":
            agg[key]["correct_total"] += 1
            if r["verdict"] == "CORRECT":
                agg[key]["correct_flag"] += 1
        else:
            agg[key]["mut_total"] += 1
            if r["verdict"] == "INCORRECT":
                agg[key]["mut_flag"] += 1

    curve = {}
    print(f"{'level':<6} {'sens':<8} {'spec':<8} {'n_mut':<6} {'n_correct':<10}")
    for lv in LEVELS:
        a = agg[lv]
        sens = a["mut_flag"] / a["mut_total"] if a["mut_total"] else None
        spec = a["correct_flag"] / a["correct_total"] if a["correct_total"] else None
        curve[lv] = {"sensitivity": sens, "specificity": spec,
                     "n_mutation": a["mut_total"], "n_correct": a["correct_total"]}
        print(f"{lv:<6} {str(round(sens,3) if sens is not None else '-'):<8} "
              f"{str(round(spec,3) if spec is not None else '-'):<8} "
              f"{a['mut_total']:<6} {a['correct_total']:<10}")

    Path(args.out).write_text(json.dumps(curve, indent=2))
    print(f"\nwrote {args.out}")

if __name__ == "__main__":
    main()
