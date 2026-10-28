#!/usr/bin/env python3
import asyncio, json, os, re, subprocess, sys, tempfile
from pathlib import Path
import aiohttp

ROOT    = Path(__file__).resolve().parent
OUT_ALL = ROOT / "state" / "proposals.jsonl"
OUT_ACC = ROOT / "state" / "accepted_classes.jsonl"
RAWD    = ROOT / "state" / "proposals_raw"
RAWD.mkdir(parents=True, exist_ok=True)
for f in (OUT_ALL, OUT_ACC):
    f.parent.mkdir(parents=True, exist_ok=True)
    if f.exists(): f.unlink()

KEY = os.environ.get("GROQ_API_KEY")
if not KEY: print("set GROQ_API_KEY", file=sys.stderr); sys.exit(3)

MODEL = "openai/gpt-oss-20b"
N_PROP = 10
N_TRIALS = 3

tax = json.loads((ROOT/"taxonomy.json").read_text())
existing = [c["name"]+" / "+c["subtype"] for c in tax.get("classes",[])]

PROMPT = ("Propose a NEW LLM coding failure class not already in this taxonomy:\n"
 + "\n".join("  - "+e for e in existing) + """

CRITICAL FIELD CONTRACT:
  - impl_src  = the CORRECT, WORKING reference implementation. It MUST pass test_src.
  - base_src  = a stub that returns None: def f(*a, **k): return None. It MUST fail test_src.
  - test_src  = asserts that MUST succeed on impl_src. Ends with print('PASS').
  - Do NOT put buggy code in impl_src. impl_src is the correct version.

The FAILURE you are proposing is described by {name, subtype, mechanism, spec}.
It is NOT represented as buggy code in impl_src — impl_src is always correct.

Correct format:
{
  "name": "off_by_one",
  "subtype": "range_boundary",
  "mechanism": "Model uses < instead of <= at range boundary",
  "spec": "Write f(n) returning list 0..n inclusive.",
  "impl_src": "def f(n):\\n    return list(range(n+1))",
  "base_src": "def f(*a, **k): return None",
  "test_src": "assert f(3) == [0,1,2,3]\\nprint('PASS')"
}

Output ONE JSON object. No prose, no markdown. impl_src MUST compile and MUST pass test_src.""")

def strip_fences(t):
    t = (t or "").strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json|python)?\s*", "", t)
        t = re.sub(r"\s*```\s*$", "", t)
    return t.strip()

def is_path(s):
    return bool(s) and s.endswith(".py") and "/" in s and "def " not in s

def parse(t):
    t2 = strip_fences(t)
    m = re.search(r"\{.*\}", t2, re.DOTALL)
    if not m: return None, "no braces"
    try: obj = json.loads(m.group(0))
    except Exception as e: return None, "json: "+str(e)
    for k in ("impl_src","base_src","test_src"):
        if is_path(obj.get(k,"")):
            return None, k+" is a path: "+str(obj[k])[:40]
    return obj, "ok"

def run(src, test, tmo=5):
    if not src: return False, "EMPTY"
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(src.rstrip()+"\n\n"+test); p = f.name
    try:
        r = subprocess.run([sys.executable,"-I",p], capture_output=True, text=True,
                           timeout=tmo, env={"PATH":os.environ.get("PATH","/usr/bin:/bin")})
        ok = (r.returncode==0) and ("PASS" in (r.stdout or ""))
        err = (r.stderr or "").strip().splitlines()
        return ok, err[-1][:100] if err else ""
    except subprocess.TimeoutExpired: return False, "TIMEOUT"
    finally:
        try: os.unlink(p)
        except OSError: pass

def g_syntax(p):
    for k in ("impl_src","base_src","test_src"):
        try: compile(p.get(k,""), "<"+k+">", "exec")
        except Exception as e: return False, "syntax "+k+": "+str(e)
    return True, "ok"

def g_disc(p):
    i_ok, i_e = run(p["impl_src"], p["test_src"])
    if not i_ok: return False, "impl fails own test: "+i_e[:80]
    b_ok, _ = run(p["base_src"], p["test_src"])
    if b_ok: return False, "baseline passes"
    return True, "discriminates"

def g_held(p):
    impl, base, test = p["impl_src"], p["base_src"], p["test_src"]
    names = set(re.findall(r'\bdef\s+([A-Za-z_]\w*)', impl)) | set(re.findall(r'\b([A-Za-z_]\w*)\s*\(', test))
    builtins = {"print","len","range","sorted","max","min","abs","int","str","list","set","dict","sum","any","all"}
    m = {n: n+"_ho" for n in names if n not in builtins and not n.startswith("_")}
    def ren(s):
        for o,n in m.items(): s = re.sub(r"\b"+re.escape(o)+r"\b", n, s)
        return s
    i_ok,_ = run(ren(impl), ren(test))
    b_ok,_ = run(ren(base), ren(test))
    return (True, "survives rename") if (i_ok and not b_ok) else (False, "impl="+str(i_ok)+" base="+str(b_ok))

def g_nov(p):
    cls = (p.get("name","")+" / "+p.get("subtype","")).strip()
    if any(e.lower()==cls.lower() for e in existing):
        return False, "duplicate of "+cls
    return True, "novel"

async def mcall(s, prompt):
    async with s.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": "Bearer "+KEY, "Content-Type": "application/json"},
        json={
            "model": MODEL,
            "messages": [
                {"role": "system", "content": "Output only raw JSON. No prose, no markdown, no fences."},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 2000,
            "temperature": 0.7,
            "response_format": {"type": "json_object"},
        },
        timeout=aiohttp.ClientTimeout(total=120)) as r:
        body = await r.text()
        if r.status != 200:
            raise RuntimeError("HTTP "+str(r.status)+": "+body[:200])
        j = json.loads(body)
        ch = j["choices"][0]
        return ch["message"].get("content") or "", ch.get("finish_reason","?"), j.get("usage",{})

async def g_emp(s, p):
    prompt = "Write a single Python function `f` satisfying:\n"+p.get("spec","")+"\nReturn ONLY the function definition."
    fails = 0
    for _ in range(N_TRIALS):
        try:
            code, _, _ = await mcall(s, prompt)
            await asyncio.sleep(4.0)
            ok, _ = run(strip_fences(code), p["test_src"])
            if not ok: fails += 1
        except Exception: pass
    return (True, "model fails "+str(fails)+"/"+str(N_TRIALS)) if fails >= 2 else (False, "fails "+str(fails)+"/"+str(N_TRIALS))

async def main():
    async with aiohttp.ClientSession() as s:
        all_r, acc = [], []
        for i in range(N_PROP):
            try:
                raw, fr, usage = await mcall(s, PROMPT)
            except Exception as e:
                print("["+str(i+1)+"/"+str(N_PROP)+"] GEN_FAIL "+type(e).__name__+": "+str(e)[:100])
                await asyncio.sleep(3.0); continue
            await asyncio.sleep(4.0)
            (RAWD / ("proposal_"+str(i+1).zfill(2)+"_raw.txt")).write_text(raw)
            print("["+str(i+1)+"/"+str(N_PROP)+"] call ok  finish="+str(fr)+"  chars="+str(len(raw))+"  tokens="+str(usage.get("completion_tokens","?")))
            p, why = parse(raw)
            if not p:
                print("       PARSE_FAIL  "+why)
                all_r.append({"proposal_num": i+1, "verdict": "PARSE_FAIL", "reason": why,
                              "finish_reason": fr, "n_chars": len(raw)})
                OUT_ALL.write_text("\n".join(json.dumps(r) for r in all_r)+"\n")
                continue
            gates = {}
            ok, why = g_syntax(p);    gates["syntax"] = {"ok":ok,"why":why}
            if ok: ok, why = g_disc(p);   gates["discriminate"] = {"ok":ok,"why":why}
            if ok: ok, why = g_held(p);   gates["heldout"] = {"ok":ok,"why":why}
            if ok: ok, why = g_nov(p);    gates["novelty"] = {"ok":ok,"why":why}
            if ok: ok, why = await g_emp(s, p); gates["empirical"] = {"ok":ok,"why":why}
            row = {"proposal_num": i+1, "name": p.get("name","?"), "subtype": p.get("subtype","?"),
                   "mechanism": p.get("mechanism",""), "gates": gates,
                   "passed_all": all(g["ok"] for g in gates.values()) and len(gates)==5}
            all_r.append(row)
            last = list(gates.keys())[-1]
            print("       "+("ACCEPT" if row["passed_all"] else "reject")+"  "+p.get("name","?")+"  last="+last+": "+gates[last]["why"][:60])
            if row["passed_all"]: acc.append(row)
            OUT_ALL.write_text("\n".join(json.dumps(r) for r in all_r)+"\n")
        OUT_ACC.write_text("\n".join(json.dumps(r) for r in acc)+"\n")
        n_pf = sum(1 for r in all_r if r.get("verdict")=="PARSE_FAIL")
        n_tested = len(all_r) - n_pf
        print("\n=== "+str(len(acc))+"/"+str(n_tested)+" accepted  ("+str(n_pf)+" PARSE_FAIL - not a result) ===")
        print("-> "+str(OUT_ALL))
        print("-> "+str(OUT_ACC))

if __name__ == "__main__":
    asyncio.run(main())
