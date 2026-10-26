#!/usr/bin/env python3
import argparse, json, os, re, sys
from pathlib import Path
from openai import OpenAI
sys.path.insert(0, "src")
from agi.reasoning.planner import SYSTEM_PROMPT, _format_tool_catalog, extract_json_object

MARK = "\n9. For fs_write"
PROMPTS = {
    "baseline": SYSTEM_PROMPT.split(MARK)[0] if MARK in SYSTEM_PROMPT else SYSTEM_PROMPT,
    "patched": SYSTEM_PROMPT,
}

TEMPLATE_RE = re.compile(
    r"\{\{[^}]+\}\}|\$\{[^}]+\}|\$\w+(\.\w+)*|"
    r"<[^>]*(?:content|output|result|step|count)[^>]*>|"
    r"\bcontents?\s+of\s+\S+|\bthe\s+contents\b|\bsame\s+as\s+\S+", re.I)

CATALOG = [
    {"name":"fs_read","description":"Read a file",
     "args_schema":{"type":"object","properties":{"path":{"type":"string"},"max_bytes":{"type":"integer"}},"required":["path"]}},
    {"name":"fs_write","description":"Write a file",
     "args_schema":{"type":"object","properties":{"path":{"type":"string"},"content":{"type":"string"},"mode":{"type":"string"}},"required":["path","content"]}},
    {"name":"fs_list","description":"List files","args_schema":{"type":"object","properties":{},"required":[]}},
    {"name":"memory_search","description":"Search memory",
     "args_schema":{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}},
    {"name":"text_regex","description":"Regex search a file",
     "args_schema":{"type":"object","properties":{"path":{"type":"string"},"pattern":{"type":"string"}},"required":["path","pattern"]}},
    {"name":"shell","description":"Run shell command",
     "args_schema":{"type":"object","properties":{"command":{"type":"string"}},"required":["command"]}},
]

def classify(content):
    if not isinstance(content, str) or not content.strip(): return "empty"
    if TEMPLATE_RE.search(content): return "placeholder"
    return "literal_or_other"

def run_bench(bench_path, n_items, client, model):
    items = [json.loads(l) for l in Path(bench_path).read_text().strip().splitlines() if l.strip()][:n_items]
    cat_text = _format_tool_catalog(CATALOG)
    print(f"\n=== {bench_path} ({len(items)} items) ===")
    rows = []
    for cond in ("baseline", "patched"):
        for it in items:
            user = f"GOAL:\n{it.get('goal','')}\n\nAVAILABLE TOOLS:\n{cat_text}\n\nProduce a JSON plan now."
            try:
                r = client.chat.completions.create(
                    model=model,
                    messages=[{"role":"system","content":PROMPTS[cond]},
                              {"role":"user","content":user}],
                    max_tokens=1024, temperature=0.0,
                    extra_body={"reasoning_effort":"low"})
                content = r.choices[0].message.content or ""
                finish = r.choices[0].finish_reason
            except Exception as e:
                content, finish = "", f"ERR:{e}"
            cls, written = "no_json", None
            if content.strip():
                try:
                    payload = extract_json_object(content)
                    steps = payload.get("steps") or ([payload] if "tool" in payload else [])
                    cls = "no_write_step"
                    for s in steps:
                        if isinstance(s, dict) and s.get("tool") == "fs_write":
                            written = (s.get("args") or {}).get("content")
                            cls = classify(written)
                            break
                except Exception:
                    cls = "no_json"
            else:
                cls = "no_output"
            rows.append({"bench": Path(bench_path).stem, "cond": cond, "item": it.get("id"),
                         "class": cls, "written": written, "finish": finish})
            print(f"  [{cond:8}] {it.get('id','?'):<20} {cls:<18} written={str(written)[:40]!r}")
    return rows

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--benches", nargs="+", required=True)
    ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--out", default="artifacts/traces/cross_family.jsonl")
    args = ap.parse_args()
    client = OpenAI(base_url=os.environ["AGI_BASE_URL"],
                    api_key=os.environ.get("AGI_API_KEY", "EMPTY"))
    model = os.environ.get("AGI_MODEL", "gpt-oss-20b")
    all_rows = []
    for b in args.benches:
        all_rows.extend(run_bench(b, args.n, client, model))
    out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as f:
        for r in all_rows: f.write(json.dumps(r) + "\n")
    print(f"\nwrote {out} ({len(all_rows)} rows)")

if __name__ == "__main__":
    main()
