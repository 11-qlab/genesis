#!/usr/bin/env python3
"""ReWOO-style baseline: same bench, but executor substitutes placeholders
by construction. If failure vanishes -> finding is 'missing standard component',
not 'model deficit'."""
import argparse, json, os, re, subprocess, sys, urllib.request, pathlib

FILL = "FILL: "  # every FILL must be resolved before this runs

def call_llm(prompt: str, model: str, base: str, key: str, temp=0.0) -> str:
    req = urllib.request.Request(
        f"{base}/chat/completions",
        data=json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temp,
        }).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)["choices"][0]["message"]["content"]

REWOO_SYS = (
    "Produce a plan as numbered steps. Use variables #E1, #E2, ... for any value "
    "you do not know at plan time. Reference prior tool outputs only via those "
    "variables. Do not inline file contents you have not read."
)

def run_one(task: dict, model, base, key) -> dict:
    prompt = f"{REWOO_SYS}\n\nTASK:\n{json.dumps(task, indent=2)}\n\nPLAN:"
    plan = call_llm(prompt, model, base, key)
    # Execute: read tool results, substitute #E<n> before each write.
    obs: dict[str, str] = {}
    seq_ok = True
    step_re = re.compile(r"^\s*(\d+)\.\s*(.*)$", re.M)
    for m in step_re.finditer(plan):
        step = m.group(2)
        tool = re.match(r"(fs_read|fs_write|shell)\((.*)\)", step)
        if not tool: continue
        name, args = tool.group(1), tool.group(2)
        # substitute any #E<n> from prior observations
        for k, v in obs.items():
            args = args.replace(f"#{k}", json.dumps(v))
        if name == "fs_read":
            path = args.strip().strip('"').strip("'")
            try:
                obs[f"E{len(obs)+1}"] = pathlib.Path(path).read_text()
            except Exception as e:
                obs[f"E{len(obs)+1}"] = f"<error: {e}>"; seq_ok = False
        elif name == "fs_write":
            # args = "path", "content"
            parts = [p.strip() for p in re.split(r',(?=")', args, maxsplit=1)]
            if len(parts) == 2:
                p = parts[0].strip('"').strip("'")
                c = parts[1].strip('"').strip("'")
                pathlib.Path(p).write_text(c)
    return {"task_id": task.get("id"), "plan": plan, "obs": obs, "seq_ok": seq_ok}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bench", default="bench/test")
    ap.add_argument("--out", default="/tmp/rewoo_baseline.jsonl")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    base = os.environ.get("AGI_BASE_URL"); model = os.environ.get("AGI_MODEL")
    key  = os.environ.get("AGI_API_KEY", "EMPTY")
    if not base or not model: sys.exit("set AGI_BASE_URL and AGI_MODEL")
    # FILL: how bench tasks are stored
    tasks = []
    for p in sorted(pathlib.Path(a.bench).rglob("*.json")):
        tasks.append(json.loads(p.read_text()))
    if a.limit: tasks = tasks[:a.limit]
    print(f"[rewoo] {len(tasks)} tasks from {a.bench}")
    pathlib.Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    with open(a.out, "w") as f:
        for t in tasks:
            r = run_one(t, model, base, key)
            f.write(json.dumps(r) + "\n")
            print(f"  {r['task_id']}: ok={r['seq_ok']} vars={len(r['obs'])}")
    print(f"[rewoo] wrote {a.out}")

if __name__ == "__main__":
    main()
