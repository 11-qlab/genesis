"""Pure-stdlib statistics for probe results."""
from __future__ import annotations
import random
from dataclasses import dataclass
from typing import Callable, Sequence

from .discrimination import ProbeResult


def discrimination_score(results, ground_truth, undecided_policy="half"):
    assert len(results) == len(ground_truth)
    correct = 0.0
    used = 0
    for r, gt in zip(results, ground_truth):
        if r.label == "undecided":
            if undecided_policy == "exclude":
                continue
            correct += 0.5
            used += 1
            continue
        used += 1
        if r.label == gt:
            correct += 1
    if used == 0:
        return float("nan"), 0, 0
    return correct / used, int(correct), used


def bootstrap_ci(sample, stat=lambda x: sum(x) / len(x), n_boot=2000, alpha=0.05, seed=0):
    rng = random.Random(seed)
    n = len(sample)
    if n == 0:
        return (float("nan"), float("nan"))
    stats = []
    for _ in range(n_boot):
        resample = [sample[rng.randrange(n)] for _ in range(n)]
        stats.append(stat(resample))
    stats.sort()
    return stats[int(alpha / 2 * n_boot)], stats[int((1 - alpha / 2) * n_boot) - 1]


def permutation_test(a, b, n_perm=5000, seed=0, two_sided=True):
    rng = random.Random(seed)
    obs = (sum(a) / len(a)) - (sum(b) / len(b)) if a and b else 0.0
    pooled = list(a) + list(b)
    na = len(a)
    hits = 0
    for _ in range(n_perm):
        rng.shuffle(pooled)
        da = sum(pooled[:na]) / na
        db = sum(pooled[na:]) / (len(pooled) - na)
        diff = da - db
        if two_sided:
            if abs(diff) >= abs(obs) - 1e-12:
                hits += 1
        else:
            if diff >= obs - 1e-12:
                hits += 1
    return (hits + 1) / (n_perm + 1)


@dataclass
class HullGap:
    inside: float
    outside: float
    gap: float
    gap_ci: tuple
    p_value: float
    n_inside: int
    n_outside: int

    def summary(self):
        lo, hi = self.gap_ci
        return (
            f"Hull gap: {self.gap:+.3f} [{lo:+.3f}, {hi:+.3f}]  "
            f"p={self.p_value:.4f}  (inside={self.inside:.3f} n={self.n_inside}, "
            f"outside={self.outside:.3f} n={self.n_outside})"
        )


def hull_gap(inside_scores, outside_scores, n_boot=2000, n_perm=5000, seed=0):
    if not inside_scores or not outside_scores:
        return HullGap(float("nan"), float("nan"), float("nan"),
                       (float("nan"), float("nan")), float("nan"),
                       len(inside_scores), len(outside_scores))
    rng = random.Random(seed)
    mi = sum(inside_scores) / len(inside_scores)
    mo = sum(outside_scores) / len(outside_scores)
    diffs = []
    for _ in range(n_boot):
        si = [inside_scores[rng.randrange(len(inside_scores))] for _ in inside_scores]
        so = [outside_scores[rng.randrange(len(outside_scores))] for _ in outside_scores]
        diffs.append(sum(si) / len(si) - sum(so) / len(so))
    diffs.sort()
    lo = diffs[int(0.025 * len(diffs))]
    hi = diffs[int(0.975 * len(diffs)) - 1]
    p = permutation_test(inside_scores, outside_scores, n_perm=n_perm, seed=seed)
    return HullGap(mi, mo, mi - mo, (lo, hi), p, len(inside_scores), len(outside_scores))


def expected_calibration_error(results, ground_truth, n_bins=10):
    bins = [[] for _ in range(n_bins)]
    for r, gt in zip(results, ground_truth):
        if r.label == "undecided":
            continue
        conf = r.confidence
        correct = 1.0 if r.label == gt else 0.0
        idx = min(n_bins - 1, int(conf * n_bins))
        bins[idx].append((conf, correct))
    total = sum(len(b) for b in bins) or 1
    ece = 0.0
    for b in bins:
        if not b:
            continue
        avg_conf = sum(c for c, _ in b) / len(b)
        avg_acc = sum(a for _, a in b) / len(b)
        ece += (len(b) / total) * abs(avg_conf - avg_acc)
    return ece
