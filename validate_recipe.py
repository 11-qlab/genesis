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
        p = s.split("\n")
        if len(p) > 1:
            s = "\n".join(p[1:])
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
    p = Path("/tmp/rv.py")
    p.write_text(code + "\n\n" + test)
    try:
        r = subprocess.run([sys.executable, str(p)], capture_output=True, text=True, timeout=15)
        return (r.returncode == 0 and "PASS" in r.stdout, (r.stderr or "")[-300:])
    except subprocess.TimeoutExpired:
        return (False, "timeout")

TASKS = {
    "valid_palindrome": {
        "subtype": "under_specification",
        "canonical": "s == s[::-1]",
        "divergence": "must filter non-alphanumeric and lowercase before comparison",
        "ambiguous": "Write a Python function is_pal(s) that returns True if s is a palindrome. Return ONLY executable code.",
        "recipe": ("Write a Python function is_pal(s) that returns True if s is a palindrome "
                   "AFTER ignoring all non-alphanumeric characters and converting to lowercase. "
                   "Empty string returns True. Return ONLY executable code."),
        "test": ("assert is_pal('A man, a plan, a canal: Panama')==True\n"
                 "assert is_pal('race a car')==False\n"
                 "assert is_pal('')==True\n"
                 "assert is_pal('0P')==False\n"
                 "print('PASS')"),
    },
    "majority_element": {
        "subtype": "prior_override_systematic",
        "canonical": "Boyer-Moore majority vote returns some candidate",
        "divergence": "must return None when no majority element exists (>n/2)",
        "ambiguous": "Write a Python function majority(lst) that returns the majority element of lst. Return ONLY executable code.",
        "recipe": ("Write a Python function majority(lst) that returns the element appearing MORE than "
                   "len(lst)/2 times. If no element appears more than len(lst)/2 times, return None. "
                   "Return ONLY executable code."),
        "test": ("assert majority([3,2,3])==3\n"
                 "assert majority([1,2,3]) is None\n"
                 "assert majority([1])==1\n"
                 "assert majority([2,2,1,1,1,2,2])==2\n"
                 "print('PASS')"),
    },
    "isomorphic_strings": {
        "subtype": "prior_override_systematic",
        "canonical": "one-way character mapping via dict",
        "divergence": "two-way mapping required; every character must map uniquely in both directions",
        "ambiguous": "Write a Python function is_iso(s, t) that returns True if s and t are isomorphic strings. Return ONLY executable code.",
        "recipe": ("Write a Python function is_iso(s, t) that returns True if s and t are isomorphic "
                   "strings, meaning characters in s can be REPLACED to get t with a one-to-one "
                   "bijective mapping (each character in s maps to exactly one in t, and vice versa). "
                   "Return ONLY executable code."),
        "test": ("assert is_iso('egg','add')==True\n"
                 "assert is_iso('foo','bar')==False\n"
                 "assert is_iso('paper','title')==True\n"
                 "assert is_iso('badc','baba')==False\n"
                 "print('PASS')"),
    },
}

MODEL = "openai/gpt-oss-120b"
K = 15
results = {}

print("Validating recipe on 3 held-out tasks — " + MODEL + " — K=" + str(K) + " per cell\n")

for task_name, cfg in TASKS.items():
    print("=== " + task_name + " (predicted subtype: " + cfg["subtype"] + ") ===")
    for variant in ("ambiguous", "recipe"):
        prompt = cfg[variant]
        passed = failed = infra = 0
        for i in range(K):
            status, code, _ = call_model(MODEL, prompt)
            if status == "ok":
                ok, _ = run_test(code, cfg["test"])
                if ok: passed += 1
                else: failed += 1
            else:
                infra += 1
        valid = passed + failed
        pv = round(passed / valid, 3) if valid else None
        results[task_name + "__" + variant] = {
            "task": task_name, "variant": variant, "subtype": cfg["subtype"],
            "canonical": cfg["canonical"], "divergence": cfg["divergence"],
            "K": K, "valid": valid, "passed": passed, "failed": failed,
            "infra": infra, "pass_valid": pv,
        }
        print("  " + variant.ljust(11) + " pass " + str(passed) + "/" + str(valid) +
              " = " + str(pv) + "  (infra=" + str(infra) + ")")
    print()

Path("signals_robust/recipe_validation.json").write_text(json.dumps(results, indent=2))

print("=== LADDER SUMMARY ===")
print("task                        subtype                      ambiguous  recipe    recovered")
print("-" * 88)
for task_name in TASKS:
    a = results[task_name + "__ambiguous"]
    r = results[task_name + "__recipe"]
    delta = (r["pass_valid"] or 0) - (a["pass_valid"] or 0)
    print(task_name.ljust(28) + a["subtype"].ljust(28) +
          str(a["pass_valid"]).rjust(10) + str(r["pass_valid"]).rjust(8) +
          ("  +" + str(round(delta, 3))).rjust(12))

print()
print("=== PREDICTION CHECK ===")
pred = {
    "valid_palindrome":  {"a_max": 0.30},
    "majority_element":  {"a_lo": 0.40, "a_hi": 0.70},
    "isomorphic_strings":{"a_lo": 0.30, "a_hi": 0.70},
}
for task_name, p in pred.items():
    a = results[task_name + "__ambiguous"]["pass_valid"]
    r = results[task_name + "__recipe"]["pass_valid"]
    amb_ok = (a <= p["a_max"] if "a_max" in p else p["a_lo"] <= a <= p["a_hi"])
    rec_ok = r >= 0.9
    print("  " + task_name.ljust(22) + " ambiguous=" + str(a) + "  " +
          ("HIT" if amb_ok else "MISS") + "   recipe=" + str(r) + "  " +
          ("HIT" if rec_ok else "MISS"))
