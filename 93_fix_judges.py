#!/usr/bin/env python3
"""93_fix_judges.py — fix three bugs in 92_judge_gates.py.

  Fix 1 (baseline): check finish_reason; if 'length', treat as INFRA not model-fail.
                    Raise max_tokens to 1200 so CoT fits.
  Fix 2 (novelty):  append ALL prior proposals regardless of category verdict
                    (duplicates can be in language_level too).
  Fix 3 (category): add explicit anti-examples; require confidence field;
                    low-confidence classifications are flagged for manual review.
  New (4a):         deterministic mechanism-text similarity pre-gate.
                    If two mechanisms share >=80% token overlap, mark duplicate
                    WITHOUT calling the LLM. Judge is a fallback, not the primary.
"""
from pathlib import Path
p = Path(__file__).resolve().parent / "92_judge_gates.py"
s = p.read_text()

# --- Fix 1: baseline capability — bigger max_tokens + finish_reason awareness ---
old_baseline = '''async def judge_baseline_capability(session):
    """Does the model pass a trivial spec? If not, empirical failures are noise."""
    fails = 0
    for _ in range(N_BASELINE_TRIALS):
        txt, _ = await _post(session, {
            "model": MODEL,
            "messages": [{"role":"user","content":f"Write a Python function satisfying:\\n{TRIVIAL_SPEC}\\nReturn only code."}],
            "max_tokens": 400, "temperature": 0.0,
        }, tmo=60)
        if txt:
            ok, _ = run(strip_fences(txt), TRIVIAL_TEST)
            if not ok: fails += 1
        else:
            fails += 1
        await asyncio.sleep(2.2)
    passes = N_BASELINE_TRIALS - fails
    return {"passes": passes, "fails": fails, "ok": fails <= 1,
            "note": f"model passed trivial spec {passes}/{N_BASELINE_TRIALS}"}'''
new_baseline = '''async def judge_baseline_capability(session):
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
            "note": f"tested {tested}/{N_BASELINE_TRIALS} (infra {infra_fails}), model_fails {model_fails}"}'''
assert old_baseline in s, "baseline block changed"
s = s.replace(old_baseline, new_baseline)

# --- Fix 2 + 4a: novelty pre-gate (deterministic) + fix prior tracking ---
old_novelty_start = 'async def judge_novelty(session, proposal, prior_accepted):'
new_novelty_start = '''def _mech_similarity(a, b):
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

async def judge_novelty(session, proposal, prior_accepted):'''
assert old_novelty_start in s, "novelty function def missing"
s = s.replace(old_novelty_start, new_novelty_start)

# --- Fix 3: category prompt with anti-examples + confidence ---
old_cat_body = '''Two categories:
A) llm_behavioral — the LLM's TRAINED PRIOR overrides the spec. Examples:
   - Model activates canonical LeetCode solution contradicting the spec
   - Different function name activates different algorithm
   SPECIFIC TO LLM TRAINING.

B) language_level — a failure HUMAN PROGRAMMERS also commonly make:
   - Mutable default argument
   - Off-by-one error
   - Missing import statement
   - Operator precedence
   LANGUAGE ECOSYSTEM failures, present in training data.

Return JSON only:
{{"category": "llm_behavioral"|"language_level", "reason": "one sentence"}}'''
new_cat_body = '''Two categories:
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
  "training_prior_evidence": "specific prior or null"}}'''
assert old_cat_body in s, "category prompt changed"
s = s.replace(old_cat_body, new_cat_body)

# --- Fix 2 continued: append ALL prior, not just ACCEPT_LLM_BEHAVIORAL ---
old_prior_append = '''            if final == "ACCEPT_LLM_BEHAVIORAL":
                prior.append(p)'''
new_prior_append = '''            # Track every proposal we've classified so far, regardless of verdict.
            # Duplicates can occur within ANY category (two language_level gotchas
            # with same mechanism are still duplicates).
            prior.append(p)'''
assert old_prior_append in s, "prior append block changed"
s = s.replace(old_prior_append, new_prior_append)

# --- Wire deterministic 4a into the per-proposal loop ---
old_judge_call = '''            print(f"[{i}/{len(accepted)}] {p['name']} / {p['subtype']}")
            nov = await judge_novelty(s, p, prior)
            await asyncio.sleep(2.2)
            cat = await judge_category(s, p)
            await asyncio.sleep(2.2)'''
new_judge_call = '''            print(f"[{i}/{len(accepted)}] {p['name']} / {p['subtype']}")
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
            await asyncio.sleep(2.2)'''
assert old_judge_call in s, "judge call block changed"
s = s.replace(old_judge_call, new_judge_call)

# --- Wire confidence into final verdict ---
old_final = '''            final = "REVIEW_REQUIRED"
            if not nov.get("is_novel", True):
                final = "REJECT_DUPLICATE"
            elif cat.get("category") == "language_level":
                final = "REJECT_LANGUAGE_LEVEL"
            elif cat.get("category") == "llm_behavioral":
                final = "ACCEPT_LLM_BEHAVIORAL"'''
new_final = '''            final = "REVIEW_REQUIRED"
            cat_conf = cat.get("confidence", "high")
            if not nov.get("is_novel", True):
                final = "REJECT_DUPLICATE"
            elif cat.get("category") == "language_level":
                final = "REJECT_LANGUAGE_LEVEL"
            elif cat.get("category") == "llm_behavioral" and cat_conf == "high":
                final = "ACCEPT_LLM_BEHAVIORAL"
            elif cat.get("category") == "llm_behavioral" and cat_conf == "low":
                final = "REVIEW_LOW_CONFIDENCE"'''
assert old_final in s, "final verdict block changed"
s = s.replace(old_final, new_final)

p.write_text(s)
print("patched 92_: 4 fixes applied")
print("  Fix 1: baseline max_tokens=1200 + finish_reason awareness")
print("  Fix 2: prior tracks ALL proposals, not just accepted")
print("  Fix 3: category prompt has anti-examples + confidence field")
print("  New 4a: deterministic mechanism-text similarity (>=80% => duplicate)")
