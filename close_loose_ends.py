import os, sys, subprocess, json, time
from pathlib import Path
from openai import OpenAI

if not os.environ.get("GROQ_API_KEY"):
    sys.exit("export GROQ_API_KEY first")

client = OpenAI(base_url="https://api.groq.com/openai/v1",
                api_key=os.environ["GROQ_API_KEY"], timeout=90)

def strip_fences(s):
    s = (s or "").strip()
    if s.startswith("```"):
        parts = s.split("\n")
        if len(parts) > 1:
            s = "\n".join(parts[1:])
        if s.rstrip().endswith("```"):
            s = s.rstrip()[:-3]
    return s.strip()

def call_model(model, prompt, max_retries=3):
    last = None
    for attempt in range(max_retries):
        try:
            r = client.chat.completions.create(
                model=model,
                messages=[{"role":"system","content":"Return ONLY executable Python."},
                          {"role":"user","content":prompt}],
                temperature=0.0, max_tokens=1500)
            c = r.choices[0]
            content = c.message.content or ""
            if not content.strip():
                return ("empty", "", "empty")
            if c.finish_reason != "stop":
                return ("truncated", strip_fences(content), "finish=" + str(c.finish_reason))
            return ("ok", strip_fences(content), None)
        except Exception as e:
            last = str(e)
            err = last.lower()
            if any(k in err for k in ["timeout","connection","network","reset","eof","broken","refused"]):
                time.sleep(2 ** attempt); continue
            if "429" in err or "rate" in err:
                time.sleep(5 * (attempt + 1)); continue
            break
    err = (last or "").lower()
    for tag, key in [("transport_fail","timeout"),("transport_fail","connection"),
                     ("api_429","429"),("api_4xx","401"),("api_5xx","500")]:
        if key in err: return (tag, None, last)
    return ("api_other", None, last)

def run_test(code, test):
    if not code or not code.strip():
        return (False, "empty")
    p = Path("/tmp/loose.py")
    p.write_text(code + "\n\n" + test)
    try:
        r = subprocess.run([sys.executable, str(p)], capture_output=True, text=True, timeout=15)
        return (r.returncode == 0 and "PASS" in r.stdout, (r.stderr or "")[-300:])
    except subprocess.TimeoutExpired:
        return (False, "timeout")

TASKS = {
    "approximately_equal": {
        "variants": {
            "rule_only": (
                "Write a Python function approximately_equal(a, b, rel=1e-9) returning True "
                "if a and b are equal within relative tolerance rel AND within an absolute "
                "tolerance that is a small nonzero value (not 0.0), so that tiny values "
                "compare equal to zero. Return ONLY executable code."
            ),
            "threshold": (
                "Write a Python function approximately_equal(a, b, rel=1e-9) returning True "
                "if a and b are equal within relative tolerance rel AND within an absolute "
                "tolerance of at least 1e-12. Return ONLY executable code."
            ),
        },
        "test": (
            "assert approximately_equal(0.1+0.2,0.3)\n"
            "assert approximately_equal(0.0,1e-12)\n"
            "assert approximately_equal(1.0,1.0)\n"
            "assert not approximately_equal(1.0,2.0)\n"
            "assert not approximately_equal(1e-9,1e9)\n"
            "print('PASS')"
        ),
    },
    "binary_search_leftmost": {
        "variants": {
            "original": (
                "Write a Python function binary_search(arr, x) that returns the index of x "
                "in sorted arr, or -1 if absent. Return ONLY executable code."
            ),
            "rule_only": (
                "Write a Python function binary_search(arr, x) that returns the LEFTMOST "
                "index of x in sorted arr (the smallest index if x appears more than once), "
                "or -1 if absent. Return ONLY executable code."
            ),
        },
        "test": (
            "assert binary_search([1,2,2,2,3], 2) == 1\n"
            "assert binary_search([1,3,5,7], 3) == 1\n"
            "assert binary_search([], 1) == -1\n"
            "assert binary_search([2,2,2], 2) == 0\n"
            "print('PASS')"
        ),
    },
}

MODEL = "openai/gpt-oss-120b"
K = 20
results = {}

print("Running loose-ends experiments on " + MODEL)
print("K=" + str(K) + " per cell\n")

for task_name, cfg in TASKS.items():
    for variant, prompt in cfg["variants"].items():
        passed = failed = infra = 0
        details = []
        for i in range(K):
            status, code, detail = call_model(MODEL, prompt)
            if status == "ok":
                ok, err = run_test(code, cfg["test"])
                if ok: passed += 1
                else: failed += 1
                details.append({"i": i, "passed": ok, "code": code[:300], "stderr": err})
            else:
                infra += 1
                details.append({"i": i, "status": status, "detail": detail})
            if (i + 1) % 5 == 0:
                print("  " + task_name + " / " + variant + "  " + str(i+1) + "/" + str(K) +
                      "  pass=" + str(passed) + " infra=" + str(infra))
        valid = passed + failed
        pv = round(passed / valid, 3) if valid else None
        results[task_name + "__" + variant] = {
            "task": task_name, "variant": variant, "K": K,
            "valid": valid, "passed": passed, "failed": failed, "infra": infra,
            "pass_valid": pv, "details": details,
        }
        print("=> " + task_name + " / " + variant + ": " + str(passed) + "/" + str(valid) +
              " = " + str(pv) + "  (infra=" + str(infra) + ")\n")

Path("signals_robust/loose_ends.json").write_text(json.dumps(results, indent=2))

print("=== FINAL SUMMARY ===")
print("cell                                        valid  passed  pass_valid  infra")
print("-" * 78)
for k, r in results.items():
    label = k.ljust(42)
    print(label + str(r["valid"]).rjust(6) + str(r["passed"]).rjust(8) +
          "  " + str(r["pass_valid"]).rjust(10) + "  " + str(r["infra"]).rjust(4))

print()
print("=== KEY COMPARISONS ===")
ae_orig = 32/49
ae_rule = results.get("approximately_equal__rule_only", {}).get("pass_valid")
ae_thr  = results.get("approximately_equal__threshold", {}).get("pass_valid")
bs_orig = results.get("binary_search_leftmost__original", {}).get("pass_valid")
bs_rule = results.get("binary_search_leftmost__rule_only", {}).get("pass_valid")

print("approximately_equal ladder:")
print("  original ('handle zero safely')    = " + str(round(ae_orig, 3)) + "   (N=49, prior run)")
print("  rule_only ('small nonzero')        = " + str(ae_rule))
print("  threshold ('at least 1e-12')       = " + str(ae_thr))

print()
print("binary_search_leftmost ladder:")
print("  original ('the index')             = " + str(bs_orig))
print("  rule_only ('the LEFTMOST index')   = " + str(bs_rule))
