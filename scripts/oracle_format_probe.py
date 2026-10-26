#!/usr/bin/env python3
"""2x2 causal probe: which intervention closes Subproblem B?

  baseline = rules 1-8 (no rule 9), no oracle value
  oracle   = rules 1-8, seed.txt contents injected
  format   = rules 1-9 (current repo prompt), no oracle value
  both     = rules 1-9, seed.txt contents injected
"""
import argparse, json, os, pathlib, re, sys, time, urllib.request

from verifier_deterministic import TEMPLATE_RE as PLACEHOLDER_RE

SYSTEM_BASE = (
    "You are the planner for an automated agent platform.\n"
    "Return ONLY a JSON object with this exact schema (no prose, no markdown fences):\n"
    '{"goal": str, "steps": [{"id": str, "title": str, "tool": str|null, '
    '"args": object, "depends_on": [str]}]}\n'
    "\n"
    "Rules:\n"
    "1. Step ids are unique and short (letters, digits, underscore).\n"
    "2. depends_on may only reference ids of steps defined earlier in the list.\n"
    "3. Every tool MUST appear in the provided tool list.\n"
    "4. Use the tool whose description best matches the goal.\n"
    "5. All `fs_*` paths are RELATIVE to the sandbox root. Never use absolute paths.\n"
    '6. For `fs_write`, `mode` accepts "overwrite" (default) or "append".\n'
    "7. When the goal uses a vague verb and does not name a specific file, "
    "prefer `fs_list` over `fs_read`.\n"
    "8. The memory store is a separate domain from the filesystem.\n"
)

RULE_9 = (
    "9. For fs_write, the 'content' argument MUST be the literal string. "
    "Do NOT use {{...}}, $X, or reference syntax. Prior step outputs "
    "are NOT auto-substituted; you must inline the actual value.\n"
)

TOOLS_CATALOG = """- fs_read: Read contents of a file.
  args:
    - path: string *required* — file path relative to sandbox root
    - max_bytes: integer — max bytes to read
- fs_write: Write content to a file.
  args:
    - path: string *required* — file path relative to sandbox root
    - content: string *required* — the literal string to write
    - mode: string — "overwrite" (default) or "append"
- fs_list: List directory contents.
  args:
    - path: string *required* — directory path relative to sandbox root
"""


def build_prompt(goal, cond, seed_name, seed_val):
    if cond in ("format", "both"):
        sys_p = SYSTEM_BASE + RULE_9
    else:
        sys_p = SYSTEM_BASE
    p = sys_p + f"\nGOAL: {goal}\n\nTOOLS:\n{TOOLS_CATALOG}\n"
    if cond in ("oracle", "both") and seed_val is not None:
        p += f"\nAdditional context: the file {seed_name!r} currently contains: {seed_val!r}\n"
    return p


def call_model(prompt, base, model, key, timeout=180):
    req = urllib.request.Request(
        f"{base}/chat/completions",
        data=json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0,
        }).encode(),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {key}"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)["choices"][0]["message"]["content"]


def extract_write_content(reply):
    if not reply:
        return None
    try:
        j = json.loads(reply)
    except Exception:
        m = re.search(r"\{.*\}", reply, re.DOTALL)
        if not m:
            return None
        try:
            j = json.loads(m.group(0))
        except Exception:
            return None
    for s in j.get("steps", []):
        if s.get("tool") == "fs_write":
            return (s.get("args") or {}).get("content")
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="process only N items")
    ap.add_argument("--bench", default="bench/families/test/fam14in.jsonl")
    ap.add_argument("--skip-dry", action="store_true")
    a = ap.parse_args()

    base = os.environ["AGI_BASE_URL"]
    model = os.environ["AGI_MODEL"]
    key = os.environ.get("AGI_API_KEY", "EMPTY")

    items = [json.loads(l) for l in pathlib.Path(a.bench).read_text().splitlines() if l.strip()]
    if a.limit:
        items = items[: a.limit]
    print(f"[probe] {len(items)} items x 4 conditions = {len(items)*4} calls")
    print(f"[probe] model={model}")
    print(f"[probe] base={base}")
    print()

    sample = items[0]
    sf = sample.get("seed_files") or {}
    sample_name = next(iter(sf.keys()), "seed.txt")
    sample_val = next(iter(sf.values()), None) if sf else None
    dry = build_prompt(sample["goal"], "baseline", sample_name, sample_val)
    print("=== DRY RENDER (baseline) ===")
    print(dry[:1200])
    print("... [truncated] ...")
    print("=== END ===")
    print()
    if not a.skip_dry:
        print("Starting in 3s (Ctrl+C to abort)...")
        time.sleep(3)

    rows = []
    for it in items:
        sf = it.get("seed_files") or {}
        seed_name = next(iter(sf.keys()), "seed.txt")
        seed_val = next(iter(sf.values()), None) if sf else None
        for cond in ("baseline", "oracle", "format", "both"):
            prompt = build_prompt(it["goal"], cond, seed_name, seed_val)
            try:
                reply = call_model(prompt, base, model, key)
            except Exception as e:
                rows.append({"item": it["id"], "cond": cond, "error": str(e)})
                print(f"  {it['id']:15s} {cond:8s} ERROR: {e}")
                continue
            content = extract_write_content(reply)
            is_ph = bool(PLACEHOLDER_RE.search(content or ""))
            wrong = seed_val is not None and not is_ph and content != seed_val
            fail = is_ph or wrong
            rows.append({
                "item": it["id"], "cond": cond,
                "content": content, "is_placeholder": is_ph,
                "wrong_literal": wrong, "fail": fail,
                "seed_val": seed_val,
            })
            tag = repr(content)[:50] if content is not None else "NONE"
            print(f"  {it['id']:15s} {cond:8s} ph={is_ph!s:5s} wrong={wrong!s:5s} {tag}")

    from collections import defaultdict
    agg = defaultdict(lambda: {"n": 0, "ph": 0, "wrong": 0, "fail": 0})
    for r in rows:
        if "fail" not in r:
            continue
        x = agg[r["cond"]]
        x["n"] += 1
        x["ph"] += int(r["is_placeholder"])
        x["wrong"] += int(r["wrong_literal"])
        x["fail"] += int(r["fail"])

    print("\n=== 2x2 RESULT ===")
    print(f"{'cond':10s} {'fail':>8s} {'placeholder':>14s} {'wrong_literal':>16s}")
    for c in ("baseline", "oracle", "format", "both"):
        x = agg[c]
        print(f"{c:10s} {x['fail']:>3d}/{x['n']:<3d} {x['ph']:>12d}    {x['wrong']:>14d}")

    out = pathlib.Path("artifacts/esf/oracle_format_probe.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"model": model, "n_items": len(items),
                                "rows": rows, "aggregate": dict(agg)}, indent=2))
    print(f"\nwrote {out}")

    n = agg["baseline"]["n"]
    b, o, f, bo = (agg[c]["fail"] for c in ("baseline", "oracle", "format", "both"))
    print("\n=== INTERPRETATION ===")
    if o < b:
        print(f"Oracle alone reduces fail: {b}/{n} -> {o}/{n}  (structural: model lacks value)")
    else:
        print(f"Oracle alone does NOT help: {b}/{n} -> {o}/{n}  (failure is deeper than value)")
    if f < b:
        print(f"Format hint reduces fail: {b}/{n} -> {f}/{n}  (contradicts paper's rule-9 claim)")
    else:
        print(f"Format hint does NOT help: {b}/{n} -> {f}/{n}  (consistent with paper)")
    print(f"Combined: {bo}/{n}")


if __name__ == "__main__":
    main()
