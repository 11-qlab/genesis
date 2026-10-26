# Directory map

| Dir | What | Written by |
|---|---|---|
| `src/agi/` | Coordinator, planner, tools, evaluation | source |
| `cfh/` | Trajectory data model, JSONL serialization | source |
| `bench/` | Task benches (`seed/`, `test/`, `families/`) | fixtures |
| `scripts/` | Analysis, verifiers, ablation, probes | tooling |
| `schemas/` | Hypothesis manifest schema | tooling |
| `hypotheses/` | Declared hypotheses H001–H006 | research |
| `results/` | Verdicts + per-class breakdowns | research |
| `docs/research/` | WORKSHOP_PAPER, LOOP_PAPER | research |
| `docs/development/` | STATUS, KNOWN_ISSUES, design docs | research |
| `artifacts/` | Traces, verifier outputs, raw data | `reproduce.sh` |
| `infra/` | Resilient eval runner | source |
| `experiments/` | Scratch runs, not paper-backing | ad hoc |
| `checkpoints/` | Model snapshots (large) | manual |
| `state/` | SQLite runs, workspaces (gitignored) | eval runs |

Note: `artifacts/` is load-bearing — `reproduce.sh` writes into it and
`results/*.json` cite specific trace files. Do not relocate.
