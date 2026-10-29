#!/usr/bin/env python3
"""Run one task family under {baseline, prompt_patch, executor_patch}.

Simulate mode (--simulate) reproduces the *shape* of the WORKSHOP_PAPER
finding for pipeline validation at $0:
  baseline      ~ 0.70 fail
  prompt_patch  ~ 0.70 fail (prompt-invariant, per the paper)
  executor_patch ~ 0.00 fail
Pass --no-simulate to call the real model + cfh tools.
"""
from __future__ import annotations
import argparse, json, os, random, sys, uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path

import families

# ----- ADAPT: bind to your real cfh tools -----
try:
    from cfh.tools import dispatch as cfh_dispatch  # type: ignore
except Exception:
    from cfh_tools_shim import dispatch as cfh_dispatch  # type: ignore

def dispatch(tool: str, args: dict) -> str:
    if cfh_dispatch is None:
        raise RuntimeError("cfh.tools.dispatch not found — see audit.log and ADAPT marker")
    return cfh_dispatch(tool, args)

# ----- ADAPT: bind to your real model call -----
def call_model(task: dict, prior_obs: str | None, condition: str) -> dict:
    """Ask the model to inline `prior_obs` into the substitution arg.

    Scope: the model fills ONLY the argument identified by expect_arg. Tool name,
    path, and every other arg come from the task dict. This is the substitution
    decision, nothing else — matches the WORKSHOP_PAPER failure class.
    """
    import json, os
    from openai import OpenAI

    system = "You are a tool-using agent. Produce tool call arguments."

    # Identify the substitution target for this task
    target_step = next(s for s in task["steps"] if s.get("expect_arg"))
    arg_key, _ = target_step["expect_arg"]

    client = OpenAI(
        base_url=os.environ.get("OPENAI_BASE_URL") or None,
        api_key=os.environ.get("OPENAI_API_KEY") or "sk-local",
    )
    base = (
        f"Task {task['id']}.\n"
        f"Tool to call: {target_step['tool']}\n"
        f"Argument keys to fill: {sorted(target_step['args'].keys())}\n"
        f"The prior tool observation was:\n{prior_obs!r}\n\n"
        f'Return ONLY JSON of the form {{"args": {{...}}}}.'
    )
    if condition == "prompt_patch":
        base += (
            f"\n\n<OBSERVATION>\n{prior_obs}\n</OBSERVATION>\n"
            f"Copy the observation character-for-character into the "
            f"`{arg_key}` argument. Do NOT summarize. Do NOT interpret. "
            f"Do NOT change word order or whitespace. "
            f"The value must equal the observation exactly."
        )
    resp = client.chat.completions.create(
        model=os.environ.get("MODEL", "openai/gpt-oss-120b"),
        temperature=0,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": base},
        ],
        response_format={"type": "json_object"},
        seed=42,
    )
    produced = json.loads(resp.choices[0].message.content)
    # The caller merges this into the existing step args
    if "args" not in produced or not isinstance(produced["args"], dict):
        raise ValueError(f"model did not return args dict: {produced!r}")
    return produced

# ------------------------------------------------

@dataclass
class RunRecord:
    run_id: str
    family: str
    task_id: str
    condition: str
    success: bool
    mode: str
    placeholder_written: bool
    error: str | None = None
    ts: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

def simulate_outcome(task: dict, condition: str, rng: random.Random) -> tuple[bool, bool]:
    if condition == "executor_patch":
        return True, False
    fail = rng.random() < 0.70
    return (not fail), fail  # placeholder_written tracks the failure mode

def run_task(task: dict, family: str, condition: str, simulate: bool, rng: random.Random) -> RunRecord:
    run_id = uuid.uuid4().hex[:12]
    try:
        if simulate:
            ok, placeholder = simulate_outcome(task, condition, rng)
            return RunRecord(run_id, family, task["id"], condition, ok, "simulate", placeholder)

        # --- real execution path ---
        prior_obs = None
        for step in task["steps"]:
            args = dict(step["args"])
            if step.get("expect_arg") and condition == "executor_patch":
                key, _ = step["expect_arg"]
                if prior_obs is None:
                    return RunRecord(run_id, family, task["id"], condition, False,
                                     "live", False, "executor: no prior observation")
                args[key] = prior_obs  # <-- the substitution fix
            if step.get("expect_arg") and condition != "executor_patch":
                key, _ = step["expect_arg"]
                if prior_obs is not None:
                    produced = call_model(task, prior_obs, condition)
                    # Merge: only override args the model returned (should be just `key`)
                    for k, v in produced.get("args", {}).items():
                        args[k] = v

            out = dispatch(step["tool"], args)
            if step.get("expect_arg"):
                key, _ = step["expect_arg"]
                got = str(args.get(key, "")).strip()
                expected = str(prior_obs).strip() if prior_obs is not None else ""
                ok = (prior_obs is not None) and (got == expected)
                placeholder = ("<" in got and "PLACEHOLDER" in got and got != expected)
                return RunRecord(run_id, family, task["id"], condition,
                                 ok, "live", placeholder)
            prior_obs = out
        return RunRecord(run_id, family, task["id"], condition, False, "live", False,
                         "task ended without a substitution step")
    except Exception as e:
        return RunRecord(run_id, family, task["id"], condition, False,
                         "simulate" if simulate else "live", False, f"{type(e).__name__}: {e}")

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--family", required=True, choices=["C", "D"])
    ap.add_argument("--condition", required=True,
                    choices=["baseline", "prompt_patch", "executor_patch"])
    ap.add_argument("--out", default="results/runs.jsonl")
    ap.add_argument("--repeats", type=int, default=1,
                    help="repeats per task (use 1 for live; >1 for simulate variance)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--simulate", action="store_true")
    args = ap.parse_args()

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed)
    tasks = families.get(args.family)
    n = 0
    with open(args.out, "a") as f:
        for task in tasks:
            for _ in range(args.repeats):
                rec = run_task(task, args.family, args.condition, args.simulate, rng)
                f.write(json.dumps(asdict(rec)) + "\n")
                n += 1
    print(f"wrote {n} records to {args.out} (family={args.family}, cond={args.condition}, "
          f"mode={'simulate' if args.simulate else 'live'})")
    return 0

if __name__ == "__main__":
    sys.exit(main())
