#!/usr/bin/env python3
"""Patch paper/claims.md: (a) count ROOT CAUSES not anchors in TOO_STRICT,
(b) remove incoherent 'remaining 0' phrasing, (c) add the discriminator-floor
limitation that a reviewer will otherwise raise."""
from pathlib import Path
p = Path(__file__).resolve().parent / "paper" / "claims.md"
s = p.read_text()

s = s.replace(
    "The 6 TOO_STRICT anchors fall into 6 distinct classes; the dominant cause is",
    "The 6 TOO_STRICT anchors have 3 root causes (impl_missing_name ×3, "
    "signature_mismatch ×2, wrong_output ×1); the dominant cause is")

s = s.replace(
    "Genesis: **3/3 classes** have an in-loop execution-verifiable oracle "
    "(known-correct vs baseline). For those classes the survey claim is falsified. "
    "For the remaining 0 it stands. The boundary is stated, measured, and "
    "reproducible via `./run_paper.sh`.",
    "Genesis: **3/3 classes** have an in-loop execution-verifiable oracle "
    "(known-correct vs baseline). This falsifies the survey claim **for the subset "
    "measured here**. It does not falsify it for the field: the oracle is limited to "
    "classes with a hand-authored reference impl (3 in this work), and each class is "
    "grounded by exactly one discriminating anchor. See limitation 4. Boundary is "
    "stated, measured, and reproducible via `./run_paper.sh`.")

s = s.rstrip() + """

4. **The discriminator is a floor, not a ceiling.** A template is declared
   discriminating iff it (a) passes against `_known_correct_for` and (b) fails
   against `_baseline_for`, which is `def f(*a, **k): return None`. This proves
   the test *rejects a null stub*. It does NOT prove the test captures the class
   semantics — `assert f(4) == 2.0` discriminates against `return None` and also
   passes many wrong implementations. Groundedness here means "rejects garbage,"
   not "uniquely identifies the correct answer." Raising this floor requires
   adversarial anchors (ACE-style), which this work does not attempt.

5. Each grounded class rests on **exactly one** discriminating anchor
   (3/9 total). Single-anchor support is thin. Reporting the count is the honest
   alternative to a false confidence interval.
"""
p.write_text(s)
print(f"patched {p}  ({len(s.splitlines())} lines)")
