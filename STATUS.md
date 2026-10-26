# STATUS

Last verified snapshot: 2026-10-27 (commit a8954fc)

## Active research

Two workshop drafts live in `docs/research/`:

- **WORKSHOP_PAPER.md** — "Two Layers of Template Failure in Tool-Using LLM Agents."
  The 70.6% placeholder finding, the two-subproblem split, the three-layer fix,
  and the verifier behavior characterization (variance + deterministic 100%).

- **LOOP_PAPER.md** — "A Reproducible Hypothesis-Testing Loop for LLM Agent
  Research." Pre-registration + McNemar + BH correction + published rejections
  as methodology contribution. 5 hypotheses, 2 pass, 2 reject, 1 scoped.

## Hypothesis ledger

`results/` contains one file per hypothesis:

| ID | Verdict | What it produced |
|---|---|---|
| H001 | NOT_A_TEST | Verifier is order-invariant (68/68) |
| H002 | PASS | LLM verifier variance (7/17 flips, p=7.8e-4) |
| H003 | REJECTED | Regex bug: text-deferral missed |
| H004 | SCOPED | Rule 9 addresses content-substitution, not planning |
| H005 | REJECTED | Equality rule subsumes semantic regex |

Rejections produced more than passes. That's the point of the loop.

## Phase table (unchanged from prior STATUS, updated)

Phases 1–6: complete.
Phase 7 (autonomous discovery loop): infrastructure complete
(schema + runner + analysis). Hypothesis *generation* is still
human-authored.
Phase 8 (multi-model generalization): not started.

## Known issues

See `docs/research/KNOWN_ISSUES.md` — six recording-layer bugs
documented, four fixed, two open. Three of them independently masked
the placeholder finding for the length of the study.

## Reproduction

```

export AGI_BASE_URL=...    # any OpenAI-compatible gpt-oss-20b
./reproduce.sh              # 30 LLM calls, ~3 min
python3 scripts/verifier_deterministic.py 
  --trajectories /tmp/n20_verifier_test.jsonl 
  --out artifacts/esf/n20_deterministic.json   # 0 LLM calls, instant

```
