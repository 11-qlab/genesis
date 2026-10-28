#!/usr/bin/env python3
"""50_quantum_oracle.py — freeze quantum reference expectations from Aer.

Each template declares `pairs`: the ZZ pairs whose expectations are summed.
  Bell     : pairs=[(0,1)]            -> <ZZ>,        expected ~ +1.0
  GHZ-3    : pairs=[(0,1),(1,2),(0,2)] -> <ZZ>+<ZZ>+<ZZ>, expected ~ +3.0
"""
import json, sys
from pathlib import Path
import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator

ROOT = Path(__file__).resolve().parent
OUTD = ROOT / "bench/quantum_anchors"; OUTD.mkdir(parents=True, exist_ok=True)

def _ghz(n=3):
    qc = QuantumCircuit(n)
    qc.h(0)
    for i in range(n - 1):
        qc.cx(i, i + 1)
    qc.measure_all()
    return qc

def _bell():
    qc = QuantumCircuit(2)
    qc.h(0); qc.cx(0, 1); qc.measure_all()
    return qc

TEMPLATES = {
    "ghz_3_even_parity": {
        "circuit": _ghz,
        "pairs": [(0, 1), (1, 2), (0, 2)],
        "analytic_expected": 3.0,
    },
    "bell_zz": {
        "circuit": _bell,
        "pairs": [(0, 1)],
        "analytic_expected": 1.0,
    },
}

def zz_expectation_from_counts(counts, pairs):
    total = sum(counts.values())
    n = len(next(iter(counts)))
    s = 0.0
    for (i, j) in pairs:
        bi, bj = n - 1 - i, n - 1 - j
        p_same = sum(v for k, v in counts.items() if k[bi] == k[bj]) / total
        s += 2 * p_same - 1
    return s

def main():
    sim = AerSimulator()
    rows = []
    for name, spec in TEMPLATES.items():
        qc = spec["circuit"]()
        tqc = transpile(qc, sim)
        counts = sim.run(tqc, shots=100_000).result().get_counts()
        exp_val = zz_expectation_from_counts(counts, spec["pairs"])
        rows.append({
            "id": f"Q{len(rows)+1:03d}",
            "name": name,
            "expected": exp_val,                        # Aer reference (used by 51_)
            "analytic_expected": spec["analytic_expected"],
            "pairs": spec["pairs"],
            "shots": 100_000,
            "counts": counts,
        })
        print(f"  {name:<24} aer_expected={exp_val:+.4f} "
              f"(analytic {spec['analytic_expected']:+.1f})")
    OUT = OUTD / "v1.jsonl"
    OUT.write_text("\n".join(json.dumps(r, sort_keys=True) for r in rows) + "\n")
    print(f"froze {len(rows)} quantum anchors -> {OUT}")

if __name__ == "__main__":
    main()
