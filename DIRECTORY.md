# Directory map

| Dir | What | Written by |
|---|---|---|
| `src/agi/` | Core coordinator, planner, tools, evaluation | (source) |
| `cfh/` | Trajectory data model, JSONL serialization | (source) |
| `bench/` | Task benches (`seed/`, `test/`, `families/`) | (fixtures) |
| `scripts/` | Analysis + experiment scripts | (tooling) |
| `schemas/` | Hypothesis manifest schema | (tooling) |
| `hypotheses/` | Declared hypotheses H001–H005 | (research) |
| `results/` | Verdicts + per-class breakdowns | (research) |
| `docs/research/` | WORKSHOP_PAPER, LOOP_PAPER, KNOWN_ISSUES | (research) |
| `artifacts/` | Traces, verifier outputs, raw data | `reproduce.sh` |
| `infra/` | Resilient eval runner | (source) |
| `state/` | SQLite runs, workspaces (gitignored) | eval runs |
