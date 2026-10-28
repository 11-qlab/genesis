#!/usr/bin/env python3
"""71_differential_oracle.py — ground function_name_trigger via differential
testing at the MODEL level, without per-name _known_correct_for impls.

Property (differential): holding spec and inputs fixed, does behavior change
when the function NAME changes? If yes, the model is name-sensitive.

This is a DIFFERENT claim than "the template discriminates". It grounds
"the model is name-triggered" without needing any reference impl.

Uses state/heldout_verdicts.jsonl to identify the three TOO_STRICT anchors
whose failure mode is impl_missing_name (A007, A008, A009) and shows what
differential grounding would recover IF the model were run for real.
This script DOES NOT call the model; it demonstrates the ORACLE structure.
That separation is deliberate: running the model is a separate experiment.
"""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parent
OUT  = ROOT / "state" / "differential_oracle.jsonl"

# Name-pair contrast: same spec, different function name. That is the mechanism.
CONTRASTS = {
    "prior_override_failure/function_name_trigger": [
        {"id":"D001","name_a":"binary_search","name_b":"find_index",
         "spec":"Return the index of the first occurrence of x in sorted arr.",
         "inputs":[[[1,2,2,3],2],[[],1],[[1],1]]},
        {"id":"D002","name_a":"binary_search","name_b":"min_heap",
         "spec":"Return the index of the first occurrence of x in sorted arr.",
         "inputs":[[[1,2,2,3],2],[[],1],[[1],1]]},
        {"id":"D003","name_a":"find_index","name_b":"smallest_k",
         "spec":"Return the index of the first occurrence of x in sorted arr.",
         "inputs":[[[1,2,2,3],2],[[],1],[[1],1]]},
    ],
}

def oracle_property(name_a, name_b, model_call):
    """model_call(name, spec, inputs) -> str (the model's code output).
    Property: same spec+inputs, different name -> same behavior (up to name).
    If behavior differs beyond a name substitution, the model is name-triggered.
    """
    def strip_name(code, name):
        import re
        # rename all occurrences of the function name to a neutral token
        return re.sub(rf'\b{re.escape(name)}\b', "F", code)
    deltas = []
    for inp in CONTRASTS["prior_override_failure/function_name_trigger"][0]["inputs"]:
        code_a = model_call(name_a, "Return the index of the first occurrence of x in sorted arr.", inp)
        code_b = model_call(name_b, "Return the index of the first occurrence of x in sorted arr.", inp)
        normalized_a = strip_name(code_a, name_a)
        normalized_b = strip_name(code_b, name_b)
        deltas.append({"input": inp, "same_after_rename": normalized_a == normalized_b})
    return all(d["same_after_rename"] for d in deltas), deltas

# Demonstration: no real model call here. Show the STRUCTURE of the oracle.
rows = []
for c in CONTRASTS["prior_override_failure/function_name_trigger"]:
    rows.append({
        "id": c["id"],
        "class": "prior_override_failure/function_name_trigger",
        "name_a": c["name_a"], "name_b": c["name_b"],
        "spec": c["spec"], "inputs": c["inputs"],
        "oracle_kind": "differential_name_contrast",
        "needs_reference_impl": False,
        "needs_baseline": False,
        "requires": "one model call per (name, input) pair; no _known_correct_for",
        "grounds": "model is name-triggered (a different claim than template discriminates)",
        "status": "oracle_defined_not_yet_executed",
    })

OUT.write_text("\n".join(json.dumps(r, sort_keys=True) for r in rows) + "\n")
print(f"defined {len(rows)} differential oracles -> {OUT}")
print()
print("To GROUND these, execute one model call per (name, input):")
print("  for each contrast: model(name_a, spec, input) and model(name_b, spec, input)")
print("  compute normalized delta; zero delta -> NOT name-triggered; nonzero -> GROUNDED.")
print()
print("[HONEST] This oracle grounds 'model is name-sensitive'.")
print("         It does NOT ground 'template is a valid discriminator'.")
print("         Those are different claims; the paper should state both.")
print()
print("It also does NOT recover systematic/stochastic: those are spec-divergent,")
print("both outcomes are structurally valid, only the spec distinguishes.")
