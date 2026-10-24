"""Adapters: bridge genesis bench artifacts into cfh data types."""
from __future__ import annotations
import json
from pathlib import Path

from .serde import trajectory_from_dict
from .types import Trajectory


FIELD_MAP = {"goal": "goal", "steps": "steps", "outcome": "outcome",
             "family": "family", "seed_files": "seed_files"}


def load_jsonl(path):
    out = []
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def records_to_trajectories(records):
    out = []
    for rec in records:
        t = trajectory_from_dict(rec)
        t.metadata["family"] = rec.get(FIELD_MAP["family"], "unknown")
        t.metadata["seed_files"] = rec.get(FIELD_MAP["seed_files"], [])
        out.append(t)
    return out


def filter_family(trajs, prefix):
    return [t for t in trajs if str(t.metadata.get("family", "")).startswith(prefix)]


def pair_by_index(inside, outside, key="item_id"):
    idx_in = {t.metadata.get(key, t.traj_id): t for t in inside}
    idx_out = {t.metadata.get(key, t.traj_id): t for t in outside}
    common = sorted(set(idx_in) & set(idx_out))
    return [(idx_in[k], idx_out[k]) for k in common]


def build_discrimination_pairs(successes, twin_fn, k_per=3):
    out = []
    for s in successes:
        if s.outcome != "success":
            continue
        for twin in twin_fn(s)[:k_per]:
            out.append((s, twin, "A"))
    return out
