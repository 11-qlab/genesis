#!/usr/bin/env python3
"""51_submit_to_ibm.py — submit frozen circuits to IBM Quantum, gate on
agreement with the frozen reference within 3-sigma of shot noise.

Fixes vs prior version:
  - pure-Python sigma (no np.float64 -> np.bool_ in JSON)
  - defensive json default=float (belt-and-suspenders)
  - suppresses SamplerV2 deprecation warning (cosmetic; API still valid in 0.50)
  - documented available backends (ibm_brisbane retired; ibm_fez is current Heron)
"""
import json, os, sys, warnings
from pathlib import Path
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
from qiskit_ibm_runtime import QiskitRuntimeService
from qiskit_ibm_runtime import SamplerV2 as Sampler

warnings.filterwarnings("ignore", category=DeprecationWarning)

ROOT = Path(__file__).resolve().parent
ANCH = ROOT / "bench/quantum_anchors/v1.jsonl"
OUTD = ROOT / "state"; OUTD.mkdir(exist_ok=True)
VERD = OUTD / "quantum_verdicts.jsonl"

TOKEN = os.environ.get("QISKIT_IBM_TOKEN") or os.environ.get("IBM_QUANTUM_TOKEN")
if not TOKEN:
    print("REFUSED: set QISKIT_IBM_TOKEN (or IBM_QUANTUM_TOKEN)", file=sys.stderr)
    sys.exit(3)

service = QiskitRuntimeService(channel="ibm_quantum_platform", token=TOKEN)

backend_name = None
if "--backend" in sys.argv:
    backend_name = sys.argv[sys.argv.index("--backend") + 1]
if backend_name:
    try:
        backend = service.backend(backend_name)
    except Exception as e:
        avail = [b.name for b in service.backends(operational=True, simulator=False)]
        print(f"REFUSED: backend {backend_name!r} not available ({e}).", file=sys.stderr)
        print(f"Available: {avail}", file=sys.stderr)
        sys.exit(4)
else:
    backend = service.least_busy(operational=True, simulator=False)
print(f"backend: {backend.name}")

import importlib.util
spec = importlib.util.spec_from_file_location("q50", ROOT / "50_quantum_oracle.py")
q50 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q50)

anchors = [json.loads(l) for l in ANCH.read_text().splitlines() if l.strip()]

def zz_expectation_from_counts(counts, pairs):
    total = sum(counts.values())
    n = len(next(iter(counts)))
    s = 0.0
    for (i, j) in pairs:
        bi, bj = n - 1 - i, n - 1 - j
        p_same = sum(v for k, v in counts.items() if k[bi] == k[bj]) / total
        s += 2 * p_same - 1
    return s

pm = generate_preset_pass_manager(backend=backend, optimization_level=3)
sampler = Sampler(mode=backend)
SHOTS = 4096

rows, passed = [], 0
for a in anchors:
    name = a["name"]
    qc = q50.TEMPLATES[name]["circuit"]()
    isa = pm.run(qc)
    job = sampler.run([isa], shots=SHOTS)
    counts = job.result()[0].data.meas.get_counts()

    pairs  = q50.TEMPLATES[name]["pairs"]
    measured = float(zz_expectation_from_counts(counts, pairs))
    sigma    = len(pairs) / (SHOTS ** 0.5)          # pure Python float
    dev_sig  = abs(measured - a["expected"]) / sigma
    grounded = bool(dev_sig <= 3.0)
    rows.append({
        "id": a["id"], "name": name, "backend": backend.name,
        "expected": float(a["expected"]), "measured": measured,
        "sigma": float(sigma), "deviation_sigma": float(dev_sig),
        "grounded": grounded, "shots": SHOTS, "counts": counts,
    })
    passed += grounded
    print(f"  {a['id']} {name:<24} expected={a['expected']:+.3f} "
          f"measured={measured:+.3f} dev={dev_sig:.2f}σ "
          f"{'PASS' if grounded else 'FAIL'}")

VERD.write_text("\n".join(json.dumps(r, sort_keys=True, default=float) for r in rows) + "\n")
print(f"\n{passed}/{len(rows)} circuits grounded on {backend.name}")
print(f"-> {VERD}")
sys.exit(0 if passed == len(rows) else 1)
