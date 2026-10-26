#!/usr/bin/env python3
"""Same test bench, N models, classify the placeholder notation each emits.
Turns a single-model observation into a taxonomy."""
import argparse, json, os, re, sys, urllib.request, pathlib

NOTATIONS = {
    "angle_bracket": re.compile(r"<[A-Z_]+:[^>]{0,60}>"),
    "double_brace":  re.compile(r"\{\{[^}]{0,60}\}\}"),
    "dollar_var":    re.compile(r"\$\{?[A-Za-z_][A-Za-z0-9_]*\}?"),
    "rewoo_hash":    re.compile(r"#E\d+"),
    "backtick_read": re.compile(r"`[^`]{0,40}read[^`]{0,40}`", re.I),
    "ellipsis":      re.compile(r"\.\.\."),
}

def classify(text: str) -> list[str]:
    return [k for k, rx in NOTATIONS.items() if rx.search(text)]

def call(prompt, model, base, key):
    req = urllib.request.Request(f"{base}/chat/completions",
        data=json.dumps({"model": model,
            "messages":[{"role":"user","content":prompt}],
            "temperature": 0.0}).encode(),
        headers={"Content-Type":"application/json","Authorization":f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)["choices"][0]["message"]["content"]

PROMPT = (
    "You are a tool-using agent. Plan how to copy the exact contents of "
    "seed.txt into out.txt. At plan time you have not read seed.txt. "
    "Write the plan as numbered steps calling fs_read(path) and fs_write(path, content). "
    "When you do not know content yet, write a placeholder in the fs_write call. "
    "No prose, plan only."
)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", required=True)
    ap.add_argument("--out", default="/tmp/notation_map.json")
    a = ap.parse_args()
    base = os.environ["AGI_BASE_URL"]; key = os.environ.get("AGI_API_KEY","EMPTY")
    out = {}
    for m in a.models:
        try:
            plan = call(PROMPT, m, base, key)
        except Exception as e:
            out[m] = {"error": str(e)}; print(f"  {m}: ERROR {e}"); continue
        tags = classify(plan)
        out[m] = {"notations": tags, "plan_excerpt": plan[:400]}
        print(f"  {m}: {tags or 'NO-PLACEHOLDER'}")
    pathlib.Path(a.out).write_text(json.dumps(out, indent=2))
    print(f"[notation] -> {a.out}")

if __name__ == "__main__":
    main()
