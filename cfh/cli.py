"""CLI entry points: python -m cfh <command>."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

from .adapters import build_discrimination_pairs, load_jsonl, records_to_trajectories
from .discrimination import DiscriminationProbe
from .llm import default_client
from .metrics import discrimination_score, hull_gap
from .serde import load_trajectory, trajectory_to_dict
from .twins import generate_shortcut_twins, generate_twins


def cmd_twins(args):
    t = load_trajectory(args.traj)
    twins = generate_twins(t, k=args.k, edits=args.edits, seed=args.seed)
    out = Path(args.out or "twins.jsonl")
    with out.open("w") as f:
        for tw in twins:
            f.write(json.dumps(trajectory_to_dict(tw)) + "\n")
    print(f"wrote {len(twins)} twins to {out}")
    return 0


def cmd_shortcut(args):
    llm = default_client()
    t = load_trajectory(args.traj)
    twins = generate_shortcut_twins(t, k=args.k, seed=args.seed, infer_fn=llm.infer_tool_result)
    out = Path(args.out or "shortcut_twins.jsonl")
    with out.open("w") as f:
        for tw in twins:
            f.write(json.dumps(trajectory_to_dict(tw)) + "\n")
    print(f"wrote {len(twins)} shortcut twins to {out}")
    return 0


def cmd_probe(args):
    llm = default_client()
    records = load_jsonl(args.artifacts)
    trajs = records_to_trajectories(records)
    successes = [t for t in trajs if t.outcome == "success"]
    triples = build_discrimination_pairs(
        successes, lambda s: generate_shortcut_twins(s, k=args.k, infer_fn=llm.infer_tool_result)
    )
    probe = DiscriminationProbe(llm, n_samples=args.samples)
    results = []
    for correct, twin, gt in triples:
        r = probe.score_pair(correct.goal, correct, twin)
        r.metadata = {"family": correct.metadata.get("family", "unknown"), "gt": gt}
        results.append(r)

    inside = [r for r in results if str(r.metadata["family"]).startswith(args.inside_prefix)]
    outside = [r for r in results if str(r.metadata["family"]).startswith(args.outside_prefix)]

    def score(rs):
        return [1.0 if r.label == r.metadata["gt"] else 0.0 for r in rs]

    si, so = score(inside), score(outside)
    if si and so:
        print(hull_gap(si, so).summary())
    else:
        acc, _, n = discrimination_score(results, [r.metadata["gt"] for r in results],
                                         undecided_policy="exclude")
        print(f"overall discrimination = {acc:.3f}  (n={n})")

    out = Path(args.out or "probe_results.jsonl")
    with out.open("w") as f:
        for r in results:
            f.write(json.dumps({**r.__dict__, "metadata": r.metadata}) + "\n")
    print(f"wrote {len(results)} probe results to {out}")
    return 0


def build_parser():
    p = argparse.ArgumentParser(prog="cfh", description="Counterfactual Hull Probe")
    sub = p.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("twins", help="generate generic near-miss twins")
    t.add_argument("traj"); t.add_argument("-k", type=int, default=5)
    t.add_argument("--edits", type=int, default=1); t.add_argument("--seed", type=int, default=0)
    t.add_argument("--out", default=""); t.set_defaults(func=cmd_twins)

    s = sub.add_parser("shortcut", help="generate self-adversarial shortcut twins")
    s.add_argument("traj"); s.add_argument("-k", type=int, default=3)
    s.add_argument("--seed", type=int, default=0); s.add_argument("--out", default="")
    s.set_defaults(func=cmd_shortcut)

    pr = sub.add_parser("probe", help="run discrimination probe over an artifacts jsonl")
    pr.add_argument("artifacts"); pr.add_argument("-k", type=int, default=3)
    pr.add_argument("--samples", type=int, default=5)
    pr.add_argument("--inside-prefix", default="fam14in")
    pr.add_argument("--outside-prefix", default="fam16out")
    pr.add_argument("--out", default=""); pr.set_defaults(func=cmd_probe)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
