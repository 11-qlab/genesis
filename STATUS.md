# STATUS

Last verified snapshot: 90be7e0 (2026-10-27)

## What this repo is

A failure-mode study, not an AGI platform. Two papers, one hypothesis ledger,
one deterministic verifier, one recorded bug class.

## Papers

- `docs/research/WORKSHOP_PAPER.md` — Two Layers of Template Failure in
  Tool-Using LLM Agents. 70.6% placeholder rate on gpt-oss-20b (n=17),
  two-subproblem split, three-layer fix, deterministic verifier 100% on
  4 content classes.
- `docs/research/LOOP_PAPER.md` — A Reproducible Hypothesis-Testing Loop.
  Pre-registration + McNemar + BH + published rejections. 5 hypotheses;
  2 pass, 2 reject, 1 scoped.

## Hypothesis ledger

| ID | Verdict | What it produced |
|---|---|---|
| H001 | NOT_A_TEST | Verifier order-invariance (68/68) |
| H002 | PASS | LLM verifier variance (7/17 mixed, 3/17 pure-LLM) |
| H003 | REJECTED | Text-deferral regex bug found and fixed |
| H004 | SCOPED | Rule 9 covers content, not planning |
| H005 | REJECTED | Equality subsumes semantic regex |
| H006 | pending | Prospective: provenance vs equality verifier |

## Known issues

`docs/development/KNOWN_ISSUES.md` — six recording-layer defects,
4 fixed, 2 open. Three independently masked the placeholder finding
for the length of the study. Coverage gate: `fail_under = 63`
(measured 68.73%). Import-linter: 2 contracts kept.

## Verification baseline

- Model: `gpt-oss-20b` (20B, Q4_K_M), temperature 0, served via ollama
  OpenAI-compatible shim.
- Endpoint used for last run: cloudflared tunnel, ephemeral. NOT part of
  the reproducibility contract — `reproduce.sh` requires the caller to
  supply `AGI_BASE_URL`.
- Reproduce into isolated dir: `ARTIFACTS_DIR=/tmp/repro_check ./reproduce.sh`.

## Verification status (2026-10-27, Path B applied)

- Controlled split (n=15) is committed and backed: seed 1/5 → 0/5 fail; test 10/10 → 10/10 fail.
- Production rate 12/17 (70.6%) is cited in WORKSHOP_PAPER.md §4.1 but has no committed trace artifact; treated as historical.
- Ground-truth asymmetry: seed bench records `expected`; test bench does not. Test-bench fail labels are harness-self-reported.
- §7 limitation added to paper describing both.

- H007 PASS (2026-10-27): causal 2x2 on fam14in (n=12, 48 calls). Oracle injection closes Subproblem B (100% -> 0%); rule 9 alone does not (100% -> 100%, notation shifted to prose). Full data: `artifacts/esf/oracle_format_probe.json`.
