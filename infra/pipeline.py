"""End-to-end experiment: health → eval in → eval out → probe → report."""
from __future__ import annotations
import json, time
from pathlib import Path

from .env import load_env, env_snapshot
from .health import require_healthy
from .runner import ResilientRunner


ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "bench" / "families" / "test"


def run_experiment(
    inside_bench: str = "fam14in",
    outside_bench: str = "fam14out",
    skip_probe: bool = False,
) -> Path:
    load_env(required=True)
    health = require_healthy()
    print(f"health: {health['base_url']} {health['latency_ms']:.0f}ms")
    print(f"models: {health['models'][:3]}")

    ts = time.strftime("%Y%m%d-%H%M%S")
    out_dir = ROOT / "artifacts" / "runs" / ts
    out_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "started_at": ts,
        "env": env_snapshot(),
        "inside_bench": inside_bench,
        "outside_bench": outside_bench,
        "health": health,
    }
    (out_dir / "metadata.json").write_text(json.dumps(meta, indent=2))

    runner = ResilientRunner(out_dir)
    print(f"\n→ {inside_bench}")
    r_in = runner.run_bench(BENCH / f"{inside_bench}.jsonl", inside_bench)
    (out_dir / "eval_in.json").write_text(json.dumps(r_in, indent=2))

    print(f"\n→ {outside_bench}")
    r_out = runner.run_bench(BENCH / f"{outside_bench}.jsonl", outside_bench)
    (out_dir / "eval_out.json").write_text(json.dumps(r_out, indent=2))

    print(f"\n{'='*60}")
    print(f"{inside_bench}:  {r_in['passed']}/{r_in['total']} = {r_in['accuracy']:.3f}")
    print(f"{outside_bench}: {r_out['passed']}/{r_out['total']} = {r_out['accuracy']:.3f}")
    gap = r_in["accuracy"] - r_out["accuracy"]
    print(f"gap: {gap:+.3f}")

    if not skip_probe:
        print(f"\n→ probe")
        try:
            from cfh.adapters import load_jsonl, records_to_trajectories
            from cfh.discrimination import DiscriminationProbe
            from cfh.llm import default_client
            from cfh.metrics import discrimination_score
            from cfh.twins import generate_twins

            trajs = records_to_trajectories(load_jsonl(runner.traj_path))
            successes = [t for t in trajs if t.outcome == "success"]
            print(f"  {len(trajs)} trajectories, {len(successes)} successes")
            if successes:
                llm = default_client()
                probe = DiscriminationProbe(llm, n_samples=3)
                results = []
                for s in successes:
                    twins = generate_twins(s, k=1, seed=0)
                    if not twins:
                        continue
                    r = probe.score_pair(s.goal, s, twins[0])
                    results.append((r, s.metadata.get("family", "unknown")))
                if results:
                    with (out_dir / "probe_results.jsonl").open("w") as f:
                        for r, fam in results:
                            f.write(json.dumps({**r.__dict__, "family": fam}) + "\n")
                    acc, correct, used = discrimination_score(
                        [r for r, _ in results], ["A"] * len(results)
                    )
                    print(f"  discrimination: {acc:.3f} ({correct}/{used})")
        except Exception as e:
            print(f"  probe skipped: {type(e).__name__}: {e}")

    print(f"\nartifacts: {out_dir}")
    return out_dir
