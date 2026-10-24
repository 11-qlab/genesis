"""Twin generation via seeded rejection sampling over mutation operators."""
from __future__ import annotations
import random
from typing import Optional, Sequence

from .mutation import DEFAULT_MUTATIONS, Mutation, ShortcutTwinMutation
from .types import Trajectory


def _apply_k(traj, ops, k, rng, max_tries=20):
    for _ in range(max_tries):
        mutated: Optional[Trajectory] = traj
        applied = 0
        for _ in range(k):
            if mutated is None:
                break
            op = rng.choice(ops)
            out = op.apply(mutated, rng)
            if out is not None and out.compute_id() != mutated.compute_id():
                mutated = out
                applied += 1
        if mutated is not None and applied == k and mutated.compute_id() != traj.compute_id():
            return mutated
    return None


def generate_twins(traj, k=5, edits=1, ops=None, seed=0):
    rng = random.Random(seed)
    ops = list(ops or DEFAULT_MUTATIONS)
    seen = {traj.compute_id()}
    out = []
    attempts = 0
    while len(out) < k and attempts < k * 40:
        attempts += 1
        t = _apply_k(traj, ops, edits, rng)
        if t is None:
            continue
        tid = t.compute_id()
        if tid in seen:
            continue
        seen.add(tid)
        t.metadata = dict(t.metadata)
        t.metadata["twin_of"] = traj.traj_id
        t.metadata["edits"] = edits
        out.append(t)
    return out


def generate_shortcut_twins(traj, k=3, seed=0, infer_fn=None):
    rng = random.Random(seed)
    op = ShortcutTwinMutation(infer_fn=infer_fn)
    seen = {traj.compute_id()}
    out = []
    tries = 0
    while len(out) < k and tries < k * 50:
        tries += 1
        t = op.apply(traj, rng)
        if t is None:
            break
        tid = t.compute_id()
        if tid in seen:
            continue
        seen.add(tid)
        t.metadata = dict(t.metadata)
        t.metadata["twin_of"] = traj.traj_id
        t.metadata["twin_kind"] = "shortcut"
        out.append(t)
    return out
