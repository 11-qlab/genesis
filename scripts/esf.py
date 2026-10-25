#!/usr/bin/env python3
"""Evidence Sufficiency Frontier experiment.

Uses 16 real wrong-content trajectories. Renders each at 5 evidence levels:
  L1: tool names only
  L2: + step titles
  L3: + args (empty, as recorded)
  L4: + observations
  L5: + actual write-content (from workspace, constructed)

Ground truth: all 16 items are WRONG (verified from workspace files).
Detection rate = fraction flagged INCORRECT.

Expected: L1-L4 = ~0.5 (content invisible), L5 = 0.9+ (content visible).
If L5 crosses: content verification needs write-args. Quantifies the floor.
If L5 stays 0.5: no content-checking faculty at any evidence level.
"""
import argparse, json, pathlib, sys, time
from collections import defaultdict

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from cfh.llm import default_client, extract_verdict

# Family-typical wrong write content (from verified workspace files)
WRONG_WRITE = {
    "fam14in": "$read_seed.content",
    "fam14out": "0",
}
CORRECT_WRITE = {
    "fam14in": "seed-01-content",
    "fam14out": "1",
}

PROMPT = (
    "You are an agent auditor. Read the goal and trajectory. "
    "State whether the trajectory correctly achieves the goal. "
    "Your ENTIRE reply must be one of two words: CORRECT or INCORRECT. "
    "No explanation."
)

def render_level(traj: dict, level: str) -> str:
    """Render trajectory at given evidence level."""
    goal = traj.get("goal", "")
    fam = traj.get("family", "unknown")
    steps = traj.get("steps") or []

    lines = [f"GOAL: {goal}", "", "TRAJECTORY:"]

    for s in steps:
        tc = s.get("tool_call") or {}
        name = tc.get("name", "")
        args = tc.get("args") or {}
        obs = s.get("observation")
        title = s.get("title", "")

        if name:  # tool call
            if level == "L1":
                lines.append(f"  CALL {name}")
            elif level == "L2":
                lines.append(f"  CALL {name}  # {title or ''}")
            elif level == "L3":
                lines.append(f"  CALL {name}({json.dumps(args)})")
            elif level == "L4":
                lines.append(f"  CALL {name}({json.dumps(args)})")
            elif level == "L5":
                # Replace empty args with actual observed write content
                if name == "fs_write":
                    new_args = dict(args)
                    if not new_args.get("content"):
                        new_args["path"] = new_args.get("path") or "answer.txt"
                        new_args["content"] = WRONG_WRITE.get(fam, "WRONG")
                    lines.append(f"  CALL {name}({json.dumps(new_args)})")
                else:
                    lines.append(f"  CALL {name}({json.dumps(args)})")

        elif obs is not None:  # observation
            if level in ("L1", "L2", "L3"):
                pass  # no observations at low levels
            elif level in ("L4", "L5"):
                obs_short = obs if len(obs) < 120 else obs[:120] + "..."
                lines.append(f"  OBS  {obs_short}")

    return "\n".join(lines)


def load_done_ids(out_path: pathlib.Path) -> set:
    if not out_path.exists():
        return set()
    done = set()
    for line in out_path.read_text().splitlines():
        try:
            r = json.loads(line)
            done.add((r["item"], r["level"]))
        except Exception:
            continue
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trajectories", default="artifacts/runs/v2-manual/trajectories.jsonl")
    ap.add_argument("--out", default="artifacts/esf/verdicts.jsonl")
    ap.add_argument("--levels", default="L1,L2,L3,L4,L5")
    ap.add_argument("--limit", type=int, default=0,
                    help="Max items (0 = all). Use 4 for smoke test.")
    args = ap.parse_args()

    out_path = pathlib.Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Load trajectories
    trajs = []
    for line in pathlib.Path(args.trajectories).read_text().splitlines():
        if not line.strip():
            continue
        t = json.loads(line)
        if t.get("outcome") == "success":
            trajs.append(t)

    if args.limit:
        trajs = trajs[: args.limit]

    levels = args.levels.split(",")
    done = load_done_ids(out_path)
    llm = default_client()

    print(f"Loaded {len(trajs)} trajectories, {len(levels)} levels = "
          f"{len(trajs) * len(levels)} calls")
    print(f"Already done: {len(done)}")

    t0 = time.time()
    for i, traj in enumerate(trajs, 1):
        item_id = traj.get("item_id", f"item-{i}")
        fam = traj.get("family", "unknown")
        for level in levels:
            key = (item_id, level)
            if key in done:
                continue
            rendered = render_level(traj, level)
            msgs = [
                {"role": "system", "content": PROMPT},
                {"role": "user", "content": rendered + "\n\nVerdict:"},
            ]
            try:
                raw = llm.complete(msgs, temperature=0.0, max_tokens=512)
                verdict = extract_verdict(raw)
            except Exception as e:
                verdict = f"ERR:{type(e).__name__}"

            row = {
                "item": item_id,
                "family": fam,
                "level": level,
                "verdict": verdict,
                "true_label": "INCORRECT",  # ground truth: all wrong
                "correct": (verdict == "INCORRECT"),
                "duration_s": round(time.time() - t0, 1),
            }
            with out_path.open("a") as f:
                f.write(json.dumps(row) + "\n")

            mark = "✓" if row["correct"] else "·"
            print(f"  [{i}/{len(trajs)}] {item_id:20s} {level:4s} → {verdict or '?':10s} {mark}")

    # Aggregate
    print()
    print("=" * 60)
    rows = [json.loads(l) for l in out_path.read_text().splitlines()]
    by_level = defaultdict(lambda: {"n": 0, "detected": 0})
    for r in rows:
        by_level[r["level"]]["n"] += 1
        if r["correct"]:
            by_level[r["level"]]["detected"] += 1

    print(f"{'level':<6}{'n':<6}{'detection':<12}{'note'}")
    for lv in levels:
        a = by_level[lv]
        if a["n"] == 0:
            continue
        rate = a["detected"] / a["n"]
        note = ""
        if lv in ("L1", "L2", "L3"):
            note = "expected ~0.5 (content invisible)"
        elif lv == "L4":
            note = "expected ~0.5 (write content still invisible)"
        elif lv == "L5":
            note = "→ pivot: >0.9 means content-verify needs write args"
        print(f"{lv:<6}{a['n']:<6}{rate:<12.3f}{note}")

    # Write summary
    summary_path = out_path.parent / "summary.json"
    summary_path.write_text(json.dumps(
        {lv: {"n": a["n"], "detected": a["detected"],
              "rate": a["detected"] / a["n"] if a["n"] else 0}
         for lv, a in by_level.items()},
        indent=2,
    ))
    print(f"\nwrote {summary_path}")


if __name__ == "__main__":
    main()
