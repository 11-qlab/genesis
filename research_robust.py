import os, sys, subprocess, json, time, getpass
from pathlib import Path
from openai import OpenAI

if not os.environ.get("GROQ_API_KEY"):
    os.environ["GROQ_API_KEY"] = getpass.getpass("Groq key: ")

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
    last_error = None
    for attempt in range(max_retries):
        try:
            r = client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": "Return ONLY executable Python."},
                          {"role": "user", "content": prompt}],
                temperature=0.0, max_tokens=1500,
            )
            choice = r.choices[0]
            content = choice.message.content or ""
            finish = choice.finish_reason
            if not content.strip():
                return ("empty", "", "empty content")
            if finish != "stop":
                return ("truncated", strip_fences(content), "finish=" + str(finish))
            return ("ok", strip_fences(content), None)
        except Exception as e:
            last_error = str(e)
            err = last_error.lower()
            if any(k in err for k in ["timeout","connection","network","ssl",
                                       "reset","eof","refused","broken","unreachable"]):
                time.sleep(2 ** attempt); continue
            if "429" in err or "rate" in err:
                time.sleep(5 * (attempt + 1)); continue
            break
    err = (last_error or "").lower()
    if any(k in err for k in ["timeout","connection","network","reset","eof","broken","refused"]):
        return ("transport_fail", None, last_error)
    if "429" in err: return ("api_429", None, last_error)
    if "401" in err or "403" in err or "auth" in err: return ("api_4xx", None, last_error)
    if "500" in err or "502" in err or "503" in err: return ("api_5xx", None, last_error)
    return ("api_other", None, last_error)

def run_test(code, test):
    if not code or not code.strip():
        return (False, "empty code")
    p = Path("/tmp/robust_run.py")
    p.write_text(code + "\n\n" + test)
    try:
        r = subprocess.run([sys.executable, str(p)], capture_output=True, text=True, timeout=15)
        return (r.returncode == 0 and "PASS" in r.stdout, (r.stderr or "")[-500:])
    except subprocess.TimeoutExpired:
        return (False, "timeout")

TASKS = {
    "approximately_equal": {
        "original": "Write a Python function approximately_equal(a,b,rel=1e-9) returning True if a and b are equal up to relative AND absolute tolerance. Handle zero safely. Return ONLY executable code.",
        "tightened": "Write a Python function approximately_equal(a,b,rel=1e-9,abs_tol=1e-12) returning True iff |a-b| <= max(rel*max(|a|,|b|), abs_tol). The default of abs_tol MUST be 1e-12, not 0.0. Return ONLY executable code.",
        "test": "assert approximately_equal(0.1+0.2,0.3)\nassert approximately_equal(0.0,1e-12)\nassert approximately_equal(1.0,1.0)\nassert not approximately_equal(1.0,2.0)\nassert not approximately_equal(1e-9,1e9)\nprint('PASS')",
    },
    "merge_intervals": {
        "original": "Write a Python function merge_intervals(intervals) that merges overlapping or touching closed intervals. Return ONLY executable code.",
        "tightened": "Write a Python function merge_intervals(intervals) that merges overlapping AND touching closed intervals (e.g. [[1,4],[4,5]] must merge to [[1,5]]). Empty list returns []. Return ONLY executable code.",
        "test": "assert merge_intervals([[1,3],[2,6],[8,10],[15,18]])==[[1,6],[8,10],[15,18]]\nassert merge_intervals([])==[]\nassert merge_intervals([[1,4],[4,5]])==[[1,5]]\nprint('PASS')",
    },
}

MODELS = ["openai/gpt-oss-120b", "qwen/qwen3.8-27b", "openai/gpt-oss-20b"]
ROUNDS = 3
K = 3

Path("signals_robust").mkdir(exist_ok=True)
all_results = []

for rnd in range(1, ROUNDS + 1):
    print("=== ROUND " + str(rnd) + " ===")
    for task_name, cfg in TASKS.items():
        for spec in ["original", "tightened"]:
            for model in MODELS:
                ok = fail = infra = empty = trunc = 0
                for i in range(K):
                    status, code, detail = call_model(model, cfg[spec])
                    if status == "ok":
                        ok += 1
                        passed, stderr = run_test(code, cfg["test"])
                        if not passed: fail += 1
                        all_results.append({"round": rnd, "task": task_name, "spec": spec,
                                            "model": model, "status": status,
                                            "passed": passed, "code": code})
                    else:
                        if status == "empty": empty += 1
                        elif status == "truncated": trunc += 1
                        else: infra += 1
                        all_results.append({"round": rnd, "task": task_name, "spec": spec,
                                            "model": model, "status": status,
                                            "passed": None, "code": code})
                pass_total = (ok - fail) / K if K else 0
                pass_valid = (ok - fail) / ok if ok else None
                label = task_name.ljust(22) + spec.ljust(11) + model.split("/")[-1].ljust(18)
                pv = str(round(pass_valid, 2)) if pass_valid is not None else "n/a"
                print(label + " valid=" + str(ok) + "/" + str(K) +
                      " pass_total=" + str(round(pass_total, 2)) +
                      " pass_valid=" + pv +
                      " infra=" + str(infra) + " empty=" + str(empty) + " trunc=" + str(trunc))

print("\n=== AGGREGATE " + str(ROUNDS) + " ROUNDS x " + str(K) + " TRIALS ===")
print("task".ljust(22) + "spec".ljust(11) + "model".ljust(18) +
      "n".rjust(4) + "valid".rjust(7) + "pass_all".rjust(11) +
      "pass_valid".rjust(13) + "infra%".rjust(9))
print("-" * 95)

agg_out = []
for task_name in TASKS:
    for spec in ["original", "tightened"]:
        for model in MODELS:
            rows = [r for r in all_results if r["task"] == task_name
                    and r["spec"] == spec and r["model"] == model]
            n = len(rows)
            n_valid = sum(1 for r in rows if r["status"] == "ok")
            n_passed = sum(1 for r in rows if r.get("passed") is True)
            n_infra = n - n_valid
            pass_all = n_passed / n if n else 0
            pass_valid = n_passed / n_valid if n_valid else None
            infra_pct = 100 * n_infra / n if n else 0
            label = task_name.ljust(22) + spec.ljust(11) + model.split("/")[-1].ljust(18)
            pv = str(round(pass_valid, 2)) if pass_valid is not None else "n/a"
            print(label + str(n).rjust(4) + str(n_valid).rjust(7) +
                  str(round(pass_all, 2)).rjust(11) +
                  pv.rjust(13) +
                  str(round(infra_pct, 1)).rjust(9))
            agg_out.append({"task": task_name, "spec": spec, "model": model,
                            "n": n, "n_valid": n_valid, "n_passed": n_passed,
                            "n_infra": n_infra,
                            "pass_all": round(pass_all, 3),
                            "pass_valid": round(pass_valid, 3) if pass_valid is not None else None,
                            "infra_pct": round(infra_pct, 1)})

Path("signals_robust/aggregate.json").write_text(json.dumps(agg_out, indent=2))
Path("signals_robust/calls.jsonl").write_text(
    "".join(json.dumps(r) + "\n" for r in all_results))
print("\nWrote signals_robust/aggregate.json and signals_robust/calls.jsonl")
