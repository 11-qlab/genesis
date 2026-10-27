# Experimental scripts (2026-10-27)

One-off scripts from the cross-model and boundary-characterization session.
Not part of the production pipeline. Preserved for provenance.

| Script | Purpose | Artifact |
|---|---|---|
| `cross_groq_fast.py` | 48-call typed_holes test, 4 Groq models | `artifacts/esf/cross_groq_typed.json` |
| `chain_test.py` | Multi-hop deferral chain (5 steps, 2 deferrals) | inline output only |
| `adversarial_matrix.py` | 7-condition prompt-pressure curve | `artifacts/esf/adversarial_matrix.json` |
| `rule9_deploy_test.py` | Rule 9 deployability (4 prohibition variants) | `artifacts/esf/rule9_deploy.json` |
| `allam_example_test.py` | One-shot example closes 7B adoption gap | `artifacts/esf/allam_example_test.json` |
| `transform_test.py` | H013 single-op transform schema (incomplete — crashed on last task) | `artifacts/esf/transform_test.json` |

Missing result files: H012 (cross-model) and H013 (transform) have raw data
in `artifacts/esf/` but no `results/H012.json` / `results/H013.json`. Writing
those is a separate task (10 min, no API calls).

Skipped scripts (kept in /tmp, unrelated): quantum simulation tests, IBM
hardware probes, bench compiler experiments.
