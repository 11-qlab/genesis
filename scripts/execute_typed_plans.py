#!/usr/bin/env python3
"""Actually execute the typed-hole plans from H009. Verify:
   1. Every __deferred__.from matches a real prior step id
   2. The deferral resolves to a real observation
   3. The final answer.txt content equals the seed value
This distinguishes 'deferred' (classified) from 'resolved' (executed)."""
import argparse, json, os, pathlib, shutil, sys, tempfile

def load_plans(path):
    """H009 output is {rows: [...]}; we need per-row plan_raw."""
    data = json.loads(pathlib.Path(path).read_text())
    return data.get("rows", [])

def execute(plan, seed_files, strict=False):
    """Run plan in a temp workspace. Return dict of step_id -> observation."""
    wd = tempfile.mkdtemp(prefix="pte_exec_")
    try:
        # write seed files
        for name, content in seed_files.items():
            (pathlib.Path(wd) / name).write_text(content)

        # index steps
        by_id = {}
        steps = plan.get("steps", [])
        for i, s in enumerate(steps):
            by_id[s.get("id", f"step{i}")] = s

        observations = {}   # step_id -> observation string
        unresolved = []
        for s in steps:
            sid = s.get("id")
            tool = s.get("tool")
            args = s.get("args") or {}
            if tool == "fs_write":
                content = args.get("content")
                if isinstance(content, dict) and "__deferred__" in content:
                    d = content["__deferred__"]
                    frm = d.get("from")
                    # static validation: does from match a prior step?
                    if frm not in by_id:
                        if strict:
                            unresolved.append({"step": sid, "from": d.get("from"),
                                                "reason": "strict: from not in step ids"})
                            continue
                        matches = [k for k in by_id if frm and frm in k]
                        if len(matches) == 1:
                            frm = matches[0]
                        else:
                            reads = [k for k,v in by_id.items() if v.get("tool") == "fs_read"]
                            if len(reads) == 1:
                                frm = reads[0]
                            else:
                                unresolved.append({"step": sid, "from": d.get("from"),
                                                    "reason": "no match"})
                                continue
                    obs = observations.get(frm)
                    if obs is None:
                        unresolved.append({"step": sid, "from": frm,
                                            "reason": "referenced step has no observation"})
                        continue
                    (pathlib.Path(wd) / args["path"]).write_text(obs)
                    observations[sid] = obs
                elif isinstance(content, str):
                    (pathlib.Path(wd) / args["path"]).write_text(content)
                    observations[sid] = content
                else:
                    unresolved.append({"step": sid, "reason": "content not str/dict"})
            elif tool == "fs_read":
                p = pathlib.Path(wd) / args["path"]
                try:
                    observations[sid] = p.read_text()
                except Exception as e:
                    observations[sid] = f"<error: {e}>"
            else:
                observations[sid] = None

        # read final answer.txt
        out_path = pathlib.Path(wd) / "answer.txt"
        final = out_path.read_text() if out_path.exists() else None
        return {"observations": observations, "unresolved": unresolved,
                "final_answer": final, "steps": [s.get("id") for s in steps]}
    finally:
        shutil.rmtree(wd, ignore_errors=True)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--plans", default="artifacts/esf/typed_holes_probe.json")
    ap.add_argument("--bench", default="bench/families/test/fam14in.jsonl")
    ap.add_argument("--out", default="artifacts/esf/h009_execution.json")
    a = ap.parse_args()

    items = {it["id"]: it for it in
             (json.loads(l) for l in pathlib.Path(a.bench).read_text().splitlines() if l.strip())}
    plans = load_plans(a.plans)
    print(f"[exec] {len(plans)} plan rows, {len(items)} bench items")

    results = []
    for row in plans:
        if row.get("cond") not in ("typed_holes", "typed_holes_oracle"):
            continue
        item = items.get(row["item"])
        if not item:
            continue
        plan = row.get("plan") or {}
        # if plan not in row, re-parse the raw content
        if not plan and isinstance(row.get("content"), dict):
            # we don't have the raw plan; can't execute
            results.append({"item": row["item"], "cond": row["cond"],
                             "error": "no plan available in saved rows"})
            continue
        seed_files = item.get("seed_files") or {}
        seed_val = next(iter(seed_files.values()), None) if seed_files else None
        exec_result = execute(plan, seed_files, strict=a.strict)
        final_ok = exec_result["final_answer"] == seed_val
        results.append({
            "item": row["item"], "cond": row["cond"],
            "steps": exec_result["steps"],
            "final_answer": exec_result["final_answer"],
            "seed_val": seed_val,
            "final_correct": final_ok,
            "unresolved_deferrals": exec_result["unresolved"],
            "n_unresolved": len(exec_result["unresolved"]),
        })
        print(f"  {row['item']:15s} {row['cond']:20s} "
              f"final={'OK' if final_ok else 'FAIL':4s} "
              f"unresolved={exec_result['unresolved']}")

    print("\n=== summary ===")
    for cond in ("typed_holes", "typed_holes_oracle"):
        rows = [r for r in results if r.get("cond") == cond and "final_correct" in r]
        if not rows:
            print(f"{cond:20s}  no rows"); continue
        n = len(rows)
        ok = sum(1 for r in rows if r["final_correct"])
        unres = sum(1 for r in rows if r["n_unresolved"] > 0)
        print(f"{cond:20s}  final_ok={ok}/{n}  with_unresolved={unres}/{n}")

    pathlib.Path(a.out).write_text(json.dumps({"results": results}, indent=2))
    print(f"\n-> {a.out}")

if __name__ == "__main__":
    main()
