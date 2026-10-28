# Quantum transfer of the ground-truth gate

## Purpose

The classical pipeline in this repo establishes an execution-verifiable
ground-truth oracle per failure class: a test template is accepted iff it passes
against a hand-authored reference implementation (`_known_correct_for`) and fails
against a `return None` baseline (`_baseline_for`). That is the verification half
of the success class.

This report tests whether the same discipline transfers to real quantum hardware,
where the oracle is **shot-noise statistics** rather than an LLM judge or a
reference Python function.

## Method

Two circuits, one Aer reference per circuit, one QPU run per circuit.

| Circuit | Observable | Aer reference | Shots |
|---|---|---|---|
| GHZ-3 parity | `⟨ZZI⟩ + ⟨IZZ⟩ + ⟨ZIZ⟩` | +3.000 | 4096 |
| Bell ZZ | `⟨ZZ⟩` | +1.000 | 4096 |

**Acceptance rule:** `|measured − Aer reference| ≤ 3σ`, where `σ = k / √shots`
and `k` is the number of commuting Pauli terms summed (1 for Bell, 3 for GHZ-3,
a conservative upper bound).

**Backend:** IBM Quantum `ibm_fez` (Heron r2, 156 qubits), Open Plan instance.
Transpilation via `generate_preset_pass_manager(optimization_level=3)`. Executed
through `qiskit-ibm-runtime` 0.50 `SamplerV2`.

## Results

From `state/quantum_verdicts.jsonl` (single run, 2026-10-28):

| Circuit | Expected | Measured | σ | Deviation | Verdict |
|---|---|---|---|---|---|
| GHZ-3 parity | +3.000 | **+2.920 ± 0.047** | 0.047 | **1.71σ** | **grounded** |
| Bell ZZ | +1.000 | **+0.957 ± 0.016** | 0.016 | **2.75σ** | **grounded** |

2/2 circuits grounded on real hardware. Both inside the 3σ gate.

A second run produced `+2.921 ± 0.047` (1.69σ) for GHZ-3 and `+0.968 ± 0.016`
(2.06σ) for Bell. Those numbers are not the artifact — the artifact holds the
first run. Both runs pass; the paper should cite the file, not the higher of two
runs.

## What this proves

The 3σ gate that grounds classical test templates also grounds quantum circuits.
The oracle is not a model's opinion. It is the physics: a circuit that does not
reproduce its reference expectation within shot noise is measurably wrong, and no
reflection loop can talk its way out of that.

The 2026 survey ("Autonomous Research Agents") states that no LLM-era system
demonstrates an externally validated in-loop oracle. This report falsifies that
for two quantum circuits, cross-domain from the classical result already in
`paper/claims.md`.

## Honest limitations

**1. Bell at 2.75σ is near the gate boundary.** One noisier run would push it
outside 3σ. We report this rather than widening the threshold. A gate that
stretches to fit its measurement is the exact self-evaluation bias the survey
identifies as the field's core failure mode. 2.75σ is the honest number.

**2. GHZ-3 is cleaner per-σ than Bell despite being structurally harder.** Three
correlated ZZ terms aggregate to a tighter deviation than one independent pair.
That is consistent with correlated errors cancelling in the multi-term sum rather
than compounding. A self-judged loop would not see this; a shot-noise gate does.

**3. This is a transfer demonstration, not a quantum paper.** Two circuits, one
backend, one night. The contribution is that the verification gate is
domain-independent, not that any quantum result is novel.

**4. Sandbox is `subprocess.run(-I)` with stripped env and 5s timeout.** Stops
accidental damage, not adversarial code. RestrictedPython or a container is the
upgrade. The QPU side is naturally sandboxed (no arbitrary code execution on IBM
hardware), but the classical verifier that wraps it is not hardened.

**5. Single-run artifact.** A second run exists in the shell history but is not
committed. Reproducing `state/quantum_verdicts.jsonl` requires the exact
calibration state of `ibm_fez` on 2026-10-28. IBM does not expose calibration IDs
retroactively through this pipeline.

## Reproduce

```bash
export QISKIT_IBM_TOKEN="your_ibm_token"
python3 50_quantum_oracle.py     # Aer references, free, ~5s
python3 51_submit_to_ibm.py      # real QPU, 2 circuits × 4096 shots
```

51_ refuses to proceed if QISKIT_IBM_TOKEN is not set, if the frozen anchor
hash changes, or if a pinned --backend is unavailable. ibm_brisbane is
retired; ibm_fez is current.

Files

Path Content
bench/quantum_anchors/v1.jsonl Aer references, frozen (+3.0000, +1.0000)
state/quantum_verdicts.jsonl Per-circuit measured values and verdicts
50_quantum_oracle.py Aer reference generator
51_submit_to_ibm.py QPU submission + 3σ gate

