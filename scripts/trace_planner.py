#!/usr/bin/env python3
"""Capture planner reasoning traces under baseline vs patched SYSTEM_PROMPT."""
import argparse, json, os, re, sys, time
from pathlib import Path
from openai import OpenAI

sys.path.insert(0, "src")
from agi.reasoning.planner import SYSTEM_PROMPT, _format_tool_catalog, extract_json_object

# ---- split prompt into the two conditions -------------------------------------
MARK = "\n9. For fs_write"
if MARK in SYSTEM_PROMPT:
    PROMPTS = {"baseline": SYSTEM_PROMPT.split(MARK)[0], "patched": SYSTEM_PROMPT}
else:
    PROMPTS = {"baseline": SYSTEM_PROMPT, "patched": SYSTEM_PROMPT +
               "\n9. For fs_write, the 'content' argument MUST be the literal string."}

PLACEHOLDER_RE = re.compile(r"\{\{|\$\{|\$read|^<[^>]+>$|<[^>]*(?:content|output|result|count|step)[^>]*>|contents? of|the contents|will be (?:substituted|resolved)|from s\d+", re.I)
FILE_AS_CONTENT = re.compile(r"^[\w./-]+\.txt$")

# ---- tool catalog -------------------------------------------------------------
def get_catalog():
    import os
    from pathlib import Path
    # Create a workspace with inN.txt files so the registry can scan them
    ws = Path("/tmp/trace_ws"); ws.mkdir(parents=True, exist_ok=True)
    for i in range(10):
        (ws / f"in{i}.txt").write_text(f"alpha{i}")
    os.environ.setdefault("AGI_FS_ROOT", str(ws))
    try:
        from agi.tools.registry import ToolRegistry
        # Try various constructor signatures
        for attempt in (
            lambda: ToolRegistry(str(ws)),
            lambda: ToolRegistry(fs_root=str(ws)),
            lambda: ToolRegistry(),
        ):
            try:
                reg = attempt()
                cat = reg.describe()
                if cat and len(str(cat)) > 100:
                    return cat, f"registry({len(cat)} tools)"
            except Exception as e:
                last_err = e
                continue
    except Exception as e:
        last_err = e
    # Fallback: hardcoded catalog with full schema
    return [{
        "name": "fs_read", "description": "Read UTF-8 text inside the sandbox root.",
        "args_schema": {"type": "object", "properties": {
            "path": {"type": "string", "description": "relative path"},
            "max_bytes": {"type": "integer", "description": "cap"}},
            "required": ["path"]},
    }, {
        "name": "fs_write", "description": "Write UTF-8 text inside the sandbox root.",
        "args_schema": {"type": "object", "properties": {
            "path": {"type": "string", "description": "relative path"},
            "content": {"type": "string", "description": "text to write"},
            "mode": {"type": "string", "description": "overwrite or append"}},
            "required": ["path", "content"]},
    }], f"hardcoded({last_err})"


def classify(args, expected=None):
    """Return (class, content) for an fs_write step."""
    c = args.get("content")
    if not isinstance(c, str) or not c.strip():
        return "empty_or_missing", c
    # Exact match to expected value = literal
    if expected and c.strip() == expected:
        return "literal", c
    # Placeholder syntax
    if PLACEHOLDER_RE.search(c):
        return "placeholder", c
    # Filename as content
    if FILE_AS_CONTENT.match(c.strip()):
        return "filename_as_content", c
    # Non-matching but not obviously a reference
    if expected:
        return "wrong_value", c
    return "literal", c

def expected_from_goal(goal):
    m = re.search(r"'([^']{1,60})'", goal or "")
    return m.group(1) if m else None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bench", default="/tmp/n20.jsonl")
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--out", default="artifacts/traces/planner_traces.jsonl")
    args = ap.parse_args()

    bench = Path(args.bench)
    if not bench.exists():
        bench = Path("bench/families/seed/fam14in.jsonl")
    items = [json.loads(l) for l in bench.read_text().strip().splitlines() if l.strip()][: args.n]
    print(f"bench={bench}  items={len(items)}")

    catalog, src = get_catalog()
    catalog_text = _format_tool_catalog(catalog)
    print(f"catalog={src}  chars={len(catalog_text)}")
    print(f"prompt chars: baseline={len(PROMPTS['baseline'])}  patched={len(PROMPTS['patched'])}")

    client = OpenAI(base_url=os.environ["AGI_BASE_URL"], api_key=os.environ.get("AGI_API_KEY", "EMPTY"))
    out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    rows, t0 = [], time.time()

    for cond in ("baseline", "patched"):
        for i, it in enumerate(items):
            user = (f"GOAL:\n{it.get('goal','')}\n\nAVAILABLE TOOLS:\n{catalog_text}\n\n"
                    "Produce a JSON plan now.")
            try:
                r = client.chat.completions.create(
                    model=os.environ.get("AGI_MODEL", "gpt-oss-20b"),
                    messages=[{"role": "system", "content": PROMPTS[cond]},
                              {"role": "user", "content": user}],
                    max_tokens=1024, temperature=0.0,
                    extra_body={"reasoning_effort": "low"},
                )
                msg = r.choices[0].message
                content = msg.content or ""
                reasoning = getattr(msg, "reasoning_content", "") or ""
                finish = r.choices[0].finish_reason
            except Exception as e:
                content, reasoning, finish = "", f"ERR {e}", "error"

            steps = []
            try:
                payload = extract_json_object(content)
                steps = payload.get("steps") or ([payload] if "tool" in payload else [])
            except Exception:
                pass

            writes = [s for s in steps if isinstance(s, dict) and s.get("tool") == "fs_write"]
            exp = expected_from_goal(it.get("goal"))
            cls, written = ("no_write", None) if not writes else classify(writes[-1].get("args") or {}, exp)

            rows.append({
                "cond": cond, "item": it.get("id"), "goal": it.get("goal"),
                "expected": expected_from_goal(it.get("goal")),
                "class": cls, "content": written, "finish": finish,
                "reasoning": reasoning, "reasoning_len": len(reasoning),
                "content_len": len(content), "n_steps": len(steps),
                "plan_raw": content[:2000],
            })
            print(f"  [{cond:8}] {it.get('id','?'):<16} {cls:<20} "
                  f"content={str(written)[:40]!r} rlen={len(reasoning)}")

    with out.open("w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")

    print(f"\nwrote {out}  ({len(rows)} calls, {time.time()-t0:.1f}s)")
    for cond in ("baseline", "patched"):
        sub = [r for r in rows if r["cond"] == cond]
        ph = sum(1 for r in sub if r["class"] == "placeholder")
        lit = sum(1 for r in sub if r["class"] == "literal")
        print(f"  {cond:8}  n={len(sub)}  placeholder={ph}  literal={lit}  "
              f"other={len(sub)-ph-lit}")

if __name__ == "__main__":
    main()
