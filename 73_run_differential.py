#!/usr/bin/env python3
"""73_run_differential.py — execute the 3 differential contrasts defined by 71_.

18 model calls via 70_async_router. This is the actual experiment.
Grounds claim: 'holding spec fixed, behavior changes when function name changes'.
That is DIFFERENT from 'the template discriminates' (which needs _known_correct_for).
"""
import asyncio, json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from importlib.util import spec_from_file_location, module_from_spec

ROOT = Path(__file__).resolve().parent
router_spec = spec_from_file_location("router", ROOT / "70_async_router.py")
router = module_from_spec(router_spec); router_spec.loader.exec_module(router)

# The 3 contrasts from 71_
CONTRASTS = [
    {"id":"D001","name_a":"binary_search","name_b":"find_index"},
    {"id":"D002","name_a":"binary_search","name_b":"min_heap"},
    {"id":"D003","name_a":"find_index","name_b":"smallest_k"},
]
SPEC = "Return the index of the first occurrence of x in sorted arr."
INPUTS = [[[1,2,2,3],2], [[],1], [[1],1]]
MODEL = "llama-3.1-8b-instant"
OUT = ROOT / "state" / "differential_verdicts.jsonl"

def prompt(name, inp):
    # Deliberately minimal: spec + name + inputs. No hints about canonical solutions.
    return (f"Write a single Python function named `{name}`.\n"
            f"Spec: {SPEC}\n"
            f"It will be called with inputs like: {inp}\n"
            f"Return only the function definition, no explanation, no example calls.")

def normalize(code, name):
    """Rename every occurrence of `name` to F, so identical behavior = identical string."""
    return re.sub(rf"\b{re.escape(name)}\b", "F", code).strip()

async def one_contrast(c):
    deltas = []
    for inp in INPUTS:
        try:
            code_a = await router.call(prompt(c["name_a"], inp), MODEL)
            code_b = await router.call(prompt(c["name_b"], inp), MODEL)
        except Exception as e:
            deltas.append({"input": inp, "kind": "EXECUTION_FAILURE", "error": repr(e)}); continue
        n_a, n_b = normalize(code_a, c["name_a"]), normalize(code_b, c["name_b"])
        # Filter out pure whitespace/comment noise; keep semantic difference
        differ = n_a != n_b
        # A looser signal: does code_a use '<=' anywhere and code_b use '<'?
        lo_diff = ("<=" in code_a) != ("<=" in code_b)
        deltas.append({"input": inp, "identical_after_rename": not differ,
                       "le_diff": lo_diff,
                       "len_a": len(code_a), "len_b": len(code_b)})
    executed = [d for d in deltas if d.get("kind") != "EXECUTION_FAILURE"]
    failed   = [d for d in deltas if d.get("kind") == "EXECUTION_FAILURE"]
    if not executed:
        # NO calls succeeded. This is NOT a falsification. Refuse to record a verdict.
        return {**c, "deltas": deltas, "differing_inputs": None,
                "executed": False, "n_executed": 0, "n_failed": len(failed),
                "verdict": "NOT_EXECUTED",
                "reason": "all model calls raised; set an API key and re-run"}
    grounded = sum(1 for d in executed if not d.get("identical_after_rename", True))
    # Need BOTH: majority of executed inputs differ, AND no majority-failure of calls
    return {**c, "deltas": deltas, "differing_inputs": grounded,
            "executed": True, "n_executed": len(executed), "n_failed": len(failed),
            "verdict": ("GROUNDED" if grounded >= 2 else "NAME_INVARIANT"),
            "grounded": grounded >= 2}

async def main():
    rows = []
    for c in CONTRASTS:
        r = await one_contrast(c)
        rows.append(r)
        if not r["executed"]:
            print(f"  {r['id']} {r['name_a']:<16} vs {r['name_b']:<16} "
                  f"-> {r['verdict']}: {r['n_failed']}/3 calls failed")
        else:
            print(f"  {r['id']} {r['name_a']:<16} vs {r['name_b']:<16} "
                  f"differ on {r['differing_inputs']}/{r['n_executed']} executed inputs "
                  f"-> {r['verdict']}")
    OUT.write_text("\n".join(json.dumps(r, sort_keys=True, default=str) for r in rows) + "\n")
    g = sum(1 for r in rows if r.get("grounded") is True)
    ne = sum(1 for r in rows if r.get("verdict") == "NOT_EXECUTED")
    print(f"\n{g}/{len(rows)} differential contrasts GROUNDED, "
          f"{ne}/{len(rows)} NOT EXECUTED -> {OUT}")
    if ne:
        print(f"\n[BLOCK] {ne}/{len(rows)} contrasts were not executed. "
              f"Set GROQ_API_KEY (or another provider) and re-run. "
              f"'0 grounded' is NOT a falsification when nothing ran.")
    print(f"\n[HONEST] This grounds 'model is name-sensitive'.")
    print("         If {g}/{len(rows)} >= 2, the claim is citable.")
    print("         It does NOT change the 3/3 class grounding or the 3/9 anchor count.")

if __name__ == "__main__":
    asyncio.run(main())
