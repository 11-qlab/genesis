#!/usr/bin/env python3
"""Render a trajectory into L1-L4 evidence-ladder texts for gpt-oss-20b verification."""
import json, sys
from pathlib import Path

LEVELS = ["L1", "L2", "L3", "L4"]

def _args_render(tool: str, args: dict, level: str) -> str:
    if level == "L1":
        return ""  # no args at all
    keys = list(args.keys())
    if level == "L2":
        # keys + structural hints, no content
        parts = []
        for k in keys:
            v = args[k]
            if k in ("path", "file", "target"):
                parts.append(f"{k}=<path:{v}>")
            elif k in ("content", "data", "pattern"):
                parts.append(f"{k}=<{k}:len={len(str(v))}>")
            else:
                parts.append(f"{k}=<{type(v).__name__}>")
        return " | ".join(parts)
    # L3 / L4: full args
    return json.dumps(args, ensure_ascii=False, indent=None)

def render_step(step: dict, level: str) -> str:
    tool = step.get("tool", step.get("name", "unknown_tool"))
    title = step.get("title", step.get("intent", tool))
    args = step.get("args", step.get("parameters", {}))
    obs = step.get("observation", step.get("output", None))

    line = f"[{tool}] {title}"
    if level != "L1":
        a = _args_render(tool, args, level)
        if a:
            line += f"  args: {a}"
    if level == "L4" and obs is not None:
        obs_str = str(obs)
        if len(obs_str) > 1200:
            obs_str = obs_str[:600] + " ...<truncated>... " + obs_str[-600:]
        line += f"\n    observation: {obs_str}"
    return line

def render_trajectory(traj: dict, level: str) -> str:
    steps = traj.get("steps", traj.get("trajectory", []))
    lines = [f"TRAJECTORY EVIDENCE — {level}", "=" * 40]
    for i, step in enumerate(steps):
        lines.append(f"Step {i}:")
        lines.append(render_step(step, level))
        lines.append("")
    return "\n".join(lines)

def main():
    if len(sys.argv) < 2:
        print("usage: esf_render_ladder.py <traj.json> [out_dir]", file=sys.stderr)
        sys.exit(1)
    src = Path(sys.argv[1])
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else src.parent / "rendered"
    out_dir.mkdir(parents=True, exist_ok=True)
    traj = json.loads(src.read_text())
    stem = src.stem
    for level in LEVELS:
        text = render_trajectory(traj, level)
        (out_dir / f"{stem}.{level}.txt").write_text(text)
        print(f"wrote {out_dir / f'{stem}.{level}.txt'}  ({len(text)} chars)")

if __name__ == "__main__":
    main()
