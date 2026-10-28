#!/usr/bin/env python3
"""92_judge_gates.py — post-hoc semantic gates on already-accepted proposals.

Adds:
  Gate 4b — semantic novelty via LLM judge (catches name-different-mechanism-same)
  Gate 4c — category tag: llm_behavioral vs language_level (informative, not reject)
  Gate 5b — baseline capability: does model pass a trivial spec?
            If not, "model fails proposed spec" measures noise, not class specificity.

No new proposals generated. Post-hoc analysis of state/proposals.jsonl.
Writes state/proposals_tagged.jsonl with judge verdicts + final classification.

Honest limitation: the judge is the same model family as the proposer.
An independence check would use a second model family; documented as future work.
"""
import asyncio, json, os, re, subprocess, sys, tempfile
from collections import Counter
from pathlib import Path
import aiohttp

ROOT    = Path(__file__).resolve().parent
IN_FILE = ROOT / "state" / "proposals.jsonl"
OUT     = ROOT / "state" / "proposals_tagged.jsonl"

KEY = os.environ.get("GROQ_API_KEY")
if not KEY: print("set GROQ_API_KEY", file=sys.stderr); sys.exit(3)

MODEL = "openai/gpt-oss-20b"
N_BASELINE_TRIALS = 3

TRIVIAL_SPEC = "Write a Python function f(x) that returns x unchanged."
TRIVIAL_TEST = "assert f(3) == 3\nassert f('a') == 'a'\nassert f([1,2]) == [1,2]\nprint('PASS')"

tax = json.loads((ROOT/"taxonomy.json").read_text())
existing = [
    {"name": c["name"], "subtype": c["subtype"], "mechanism": (c.get("mechanism") or "")[:300]}
    for c in tax.get("classes", [])
]

def strip_fences(t):
    t = (t or "").strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json|python)?\s*", "", t)
        t = re.sub(r"\s*```\s*$", "", t)
    return t.strip()

def run(src, test, tmo=5):
    if not src: return False, "EMPTY"
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(src.rstrip() + "\n\n" + test); p = f.name
    try:
        r = subprocess.run([sys.executable,"-I",p], capture_output=True, text=True, timeout=tmo,
                           env={"PATH": os.environ.get("PATH","/usr/bin:/bin")})
        ok = (r.returncode==0) and ("PASS" in (r.stdout or ""))
        err = (r.stderr or "").strip().splitlines()
        return ok, (err[-1][:120] if err else "")
    except subprocess.TimeoutExpired: return False, "TIMEOUT"
    finally:
        try: os.unlink(p)
        except OSError: pass

async def _post(session, payload, tmo=60):
    async with session.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
        json=payload, timeout=aiohttp.ClientTimeout(total=tmo)) as r:
        if r.status != 200:
            return None, f"HTTP {r.status}: {(await r.text())[:150]}"
        try:
            return (await r.json())["choices"][0]["message"]["content"], "ok"
        except Exception as e:
            return None, f"parse: {e}"

def _mech_similarity(a, b):
    """Deterministic token-overlap similarity on mechanism text.
    >= 0.80 means treat as duplicate without calling the LLM."""
    import re
    def toks(t):
        t = (t or "").lower()
        return set(re.findall(r"[a-z]{4,}", t))
    ta, tb = toks(a), toks(b)
    if not ta or not tb: return 0.0
    return len(ta & tb) / min(len(ta), len(tb))

def check_dup_by_text(proposal, prior):
    """Deterministic 4a: mechanism string similarity vs existing + prior."""
    best, who = 0.0, None
    for c in existing:
        m = _mech_similarity(proposal.get("mechanism",""), c.get("mechanism",""))
        if m > best: best, who = m, f"{c['name']}/{c['subtype']}"
    for p in prior:
        m = _mech_similarity(proposal.get("mechanism",""), p.get("mechanism",""))
        if m > best: best, who = m, f"{p['name']}/{p['subtype']} (prior)"
    return (best >= 0.80, best, who)

async def judge_novelty(session, proposal, prior_accepted):
    existing_txt = "\n".join(
        f"  {c['name']}/{c['subtype']}: {c['mechanism'][:150]}" for c in existing)
    prior_txt = "\n".join(
        f"  {p['name']}/{p['subtype']}: {(p.get('mechanism') or '')[:150]}"
        for p in prior_accepted) or "  (none yet in this run)"
    prompt = f"""Compare this PROPOSED failure class against existing classes and previously-accepted proposals.

PROPOSED:
  {proposal['name']} / {proposal['subtype']}
  mechanism: {proposal.get('mechanism','')}

EXISTING TAXONOMY:
{existing_txt}

PRIOR ACCEPTED PROPOSALS (this run):
{prior_txt}

Question: Is the PROPOSED class semantically DISTINCT from all above?
Focus on the FAILURE MECHANISM, not the name. Same mechanism + different name = duplicate.

Return JSON only:
{{"is_novel": true|false, "duplicate_of": "name/subtype or null", "reason": "one sentence"}}"""
    txt, why = await _post(session, {
        "model": MODEL,
        "messages": [{"role":"user","content":prompt}],
        "max_tokens": 300, "temperature": 0.0,
        "response_format": {"type":"json_object"},
    })
    if txt is None:
        return {"is_novel": True, "reason": f"judge failed: {why}", "judge_failed": True}
    try: return json.loads(strip_fences(txt))
    except Exception:
        return {"is_novel": True, "reason": f"parse failed: {txt[:100]}", "judge_failed": True}

async def judge_category(session, proposal):
    prompt = f"""Categorize this LLM coding failure class.

PROPOSED:
  name: {proposal['name']}
  mechanism: {proposal.get('mechanism','')}
  spec: {proposal.get('spec','')[:300]}

Two categories:
A) llm_behavioral — the LLM's TRAINED PRIOR overrides the spec. Criteria:
   - Model activates a canonical solution to a DIFFERENT problem (LeetCode-56 merge intervals)
   - Model's behavior depends on function NAME, not spec
   - Model reproduces a known training-data pattern that contradicts the spec
   REQUIRES: the failure exists BECAUSE the model was trained on certain data.

B) language_level — a failure HUMAN PROGRAMMERS commonly make. Criteria:
   - Mutable default argument
   - Off-by-one error
   - Missing import statement
   - Operator precedence
   - Returning wrong TYPE when spec says type X (junior mistake, not training prior)
   - Unused variable, wrong variable name
   LANGUAGES AND HUMANS share these; the LLM is not special here.

EXAMPLES you must correctly classify:
  "returns a string instead of a list"          → language_level (junior type error)
  "uses < instead of <= at the loop bound"      → language_level (off-by-one)
  "reproduces LeetCode-56 merge for spec X"     → llm_behavioral (canonical solution prior)
  "different function name yields different impl" → llm_behavioral (name-triggered prior)

If genuinely ambiguous, use llm_behavioral ONLY if you can name a specific
training-data prior (e.g. LeetCode problem number, common library API, etc.).

Return JSON only:
{{"category": "llm_behavioral"|"language_level",
  "confidence": "high"|"low",
  "reason": "one sentence",
  "training_prior_evidence": "specific prior or null"}}"""
    txt, why = await _post(session, {
        "model": MODEL,
        "messages": [{"role":"user","content":prompt}],
        "max_tokens": 300, "temperature": 0.0,
        "response_format": {"type":"json_object"},
    })
    if txt is None:
        return {"category": "unknown", "reason": f"judge failed: {why}"}
    try: return json.loads(strip_fences(txt))
    except Exception:
        return {"category": "unknown", "reason": f"parse failed: {txt[:100]}"}

async def judge_baseline_capability(session):
    """Does the model pass a trivial spec?
    INFRA failures (empty content, finish_reason=length) are NOT counted as
    model failures — they mean CoT didn't fit, not that the model can't solve."""
    model_fails = 0
    infra_fails = 0
    notes = []
    for _ in range(N_BASELINE_TRIALS):
        async with session.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
            json={"model": MODEL,
                  "messages": [{"role":"user","content":TRIVIAL_SPEC + " Return only the function definition."}],
                  "max_tokens": 1200, "temperature": 0.0},
            timeout=aiohttp.ClientTimeout(total=60)) as r:
            if r.status != 200:
                infra_fails += 1; notes.append(f"HTTP {r.status}"); await asyncio.sleep(2.2); continue
            j = await r.json()
        ch = j["choices"][0]
        fr = ch.get("finish_reason", "?")
        content = ch["message"].get("content") or ""
        if fr == "length" or not content.strip():
            infra_fails += 1; notes.append(f"infra: finish={fr} chars={len(content)}")
            await asyncio.sleep(2.2); continue
        ok, err = run(strip_fences(content), TRIVIAL_TEST)
        if not ok:
            model_fails += 1; notes.append(f"model_fail: {err[:60]}")
        else:
            notes.append("pass")
        await asyncio.sleep(2.2)
    tested = N_BASELINE_TRIALS - infra_fails
    ok = (tested >= 2) and (model_fails <= 1)
    return {"model_fails": model_fails, "infra_fails": infra_fails,
            "tested": tested, "ok": ok, "notes": notes,
            "note": f"tested {tested}/{N_BASELINE_TRIALS} (infra {infra_fails}), model_fails {model_fails}"}

async def main():
    rows = [json.loads(l) for l in IN_FILE.read_text().splitlines() if l.strip()]
    accepted = [r for r in rows if r.get("passed_all")]
    print(f"loaded {len(rows)} proposals, {len(accepted)} passed all 5 gates\n")

    async with aiohttp.ClientSession() as s:
        print("=== baseline capability check ===")
        baseline = await judge_baseline_capability(s)
        print(f"  {baseline['note']}  ok={baseline['ok']}\n")
        if not baseline["ok"]:
            print("WARNING: model cannot reliably solve a trivial spec.")
            print("         Empirical gate (model fails proposed spec) measures noise, not class specificity.\n")

        prior, out = [], []
        for i, p in enumerate(accepted, 1):
            print(f"[{i}/{len(accepted)}] {p['name']} / {p['subtype']}")
            # Deterministic pre-gate 4a: mechanism text similarity
            is_dup_text, sim_score, dup_of = check_dup_by_text(p, prior)
            if is_dup_text:
                nov = {"is_novel": False, "reason": f"deterministic: {sim_score:.0%} overlap with {dup_of}",
                       "source": "text_similarity"}
                print(f"  novelty   : False  [DET] {sim_score:.0%} overlap with {dup_of}")
            else:
                nov = await judge_novelty(s, p, prior)
                nov["source"] = "llm_judge"
                await asyncio.sleep(2.2)
                print(f"  novelty   : {nov.get('is_novel')}  [LLM] {str(nov.get('reason',''))[:60]}")
            cat = await judge_category(s, p)
            await asyncio.sleep(2.2)

            final = "REVIEW_REQUIRED"
            cat_conf = cat.get("confidence", "high")
            if not nov.get("is_novel", True):
                final = "REJECT_DUPLICATE"
            elif cat.get("category") == "language_level":
                final = "REJECT_LANGUAGE_LEVEL"
            elif cat.get("category") == "llm_behavioral" and cat_conf == "high":
                final = "ACCEPT_LLM_BEHAVIORAL"
            elif cat.get("category") == "llm_behavioral" and cat_conf == "low":
                final = "REVIEW_LOW_CONFIDENCE"

            tagged = {**p, "judge_novelty": nov, "judge_category": cat,
                      "baseline_capability": baseline, "final_verdict": final}
            out.append(tagged)

            print(f"  novelty   : {nov.get('is_novel')}  {str(nov.get('reason',''))[:70]}")
            print(f"  category  : {cat.get('category')}  {str(cat.get('reason',''))[:70]}")
            print(f"  → {final}\n")

            # Track every proposal we've classified so far, regardless of verdict.
            # Duplicates can occur within ANY category (two language_level gotchas
            # with same mechanism are still duplicates).
            prior.append(p)

    OUT.write_text("\n".join(json.dumps(r) for r in out) + "\n")

    print("=== FINAL ===")
    verdicts = Counter(r["final_verdict"] for r in out)
    for v, n in verdicts.most_common():
        print(f"  {v}: {n}")
    print(f"\n-> {OUT}")

if __name__ == "__main__":
    asyncio.run(main())
