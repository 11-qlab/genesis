#!/usr/bin/env python3
"""Two patches:
  A) 73_ must distinguish 'executed, model is name-invariant' from 'never executed'
     It currently records grounded=false for both. That is a false negative.
  B) 70_ ready() must return False when the provider's env var is unset.
"""
from pathlib import Path

# --- Patch 70_ ---
p70 = Path(__file__).resolve().parent / "70_async_router.py"
s = p70.read_text()
old = '''    def ready(self):
        self._prune(); return len(self.calls) < self.rpm'''
new = '''    def ready(self, env_var=None):
        import os as _os
        if env_var and not _os.environ.get(env_var): return False
        self._prune(); return len(self.calls) < self.rpm'''
assert old in s, "70_ pattern not found"
s = s.replace(old, new)
# and the --status caller must pass the env var
s = s.replace(
    '''            print(f"{n:<10} {len(b.calls)}/{b.rpm:<3} key={'set' if key else 'MISSING':<8} ready={b.ready()}")''',
    '''            print(f"{n:<10} {len(b.calls)}/{b.rpm:<3} key={'set' if key else 'MISSING':<8} ready={b.ready(PROVIDERS[n]['env'])}")''')
p70.write_text(s)
print("patched 70_async_router.py: ready() checks key presence")

# --- Patch 73_ ---
p73 = Path(__file__).resolve().parent / "73_run_differential.py"
s = p73.read_text()
old = '''        try:
            code_a = await router.call(prompt(c["name_a"], inp), MODEL)
            code_b = await router.call(prompt(c["name_b"], inp), MODEL)
        except Exception as e:
            deltas.append({"input": inp, "error": repr(e)}); continue'''
new = '''        try:
            code_a = await router.call(prompt(c["name_a"], inp), MODEL)
            code_b = await router.call(prompt(c["name_b"], inp), MODEL)
        except Exception as e:
            deltas.append({"input": inp, "kind": "EXECUTION_FAILURE", "error": repr(e)}); continue'''
assert old in s, "73_ pattern not found (calls block)"
s = s.replace(old, new)

old2 = '''    grounded = sum(1 for d in deltas if not d.get("identical_after_rename", True)
                   and not d.get("error"))
    return {**c, "deltas": deltas, "differing_inputs": grounded,
            "grounded": grounded >= 2}   # majority of inputs differ -> name-sensitive'''
new2 = '''    executed = [d for d in deltas if d.get("kind") != "EXECUTION_FAILURE"]
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
            "grounded": grounded >= 2}'''
assert old2 in s, "73_ pattern not found (verdict block)"
s = s.replace(old2, new2)

old3 = '''        r = await one_contrast(c)
        rows.append(r)
        print(f"  {r['id']} {r['name_a']:<16} vs {r['name_b']:<16} "
              f"differ on {r['differing_inputs']}/3 inputs -> "
              f"{'GROUNDED' if r['grounded'] else 'not grounded'}")'''
new3 = '''        r = await one_contrast(c)
        rows.append(r)
        if not r["executed"]:
            print(f"  {r['id']} {r['name_a']:<16} vs {r['name_b']:<16} "
                  f"-> {r['verdict']}: {r['n_failed']}/3 calls failed")
        else:
            print(f"  {r['id']} {r['name_a']:<16} vs {r['name_b']:<16} "
                  f"differ on {r['differing_inputs']}/{r['n_executed']} executed inputs "
                  f"-> {r['verdict']}")'''
assert old3 in s, "73_ pattern not found (print block)"
s = s.replace(old3, new3)

# and the final summary must not claim grounding on non-executed
s = s.replace(
    '''    g = sum(1 for r in rows if r["grounded"])''',
    '''    g = sum(1 for r in rows if r.get("grounded") is True)
    ne = sum(1 for r in rows if r.get("verdict") == "NOT_EXECUTED")''')
s = s.replace(
    '''    print(f"\\n{g}/{len(rows)} differential contrasts grounded -> {OUT}")''',
    '''    print(f"\\n{g}/{len(rows)} differential contrasts GROUNDED, "
          f"{ne}/{len(rows)} NOT EXECUTED -> {OUT}")
    if ne:
        print(f"\\n[BLOCK] {ne}/{len(rows)} contrasts were not executed. "
              f"Set GROQ_API_KEY (or another provider) and re-run. "
              f"'0 grounded' is NOT a falsification when nothing ran.")''')

p73.write_text(s)
print("patched 73_run_differential.py: distinguishes NOT_EXECUTED from NAME_INVARIANT")
