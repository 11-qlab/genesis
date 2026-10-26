"""Statistical primitives for the hypothesis-testing loop."""
from math import comb
from typing import Iterable, Sequence


def mcnemar_exact(a: int, b: int) -> float:
    """Exact two-sided McNemar. a=discordant favoring B, b=discordant favoring A."""
    n = a + b
    if n == 0:
        return 1.0
    k = min(a, b)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / (2 ** n))


def bayes_factor_binomial(k: int, n: int, p_alt: float, p_null: float = 0.5) -> float:
    """BF10 for Binomial(k;n,p_alt) vs Binomial(k;n,p_null)."""
    if n == 0:
        return 1.0
    if p_alt in (0.0, 1.0) or p_null in (0.0, 1.0):
        return float("inf") if k / n == p_alt else 0.0
    llr = 0.0
    if k > 0:
        llr += k * (p_alt ** k).__class__(1) and k * (__import__("math").log(p_alt / p_null))
    if n - k > 0:
        llr += (n - k) * __import__("math").log((1 - p_alt) / (1 - p_null))
    import math
    return math.exp(llr)


def bf_mcnemar(b: int, c: int) -> float:
    """BF10 for McNemar counts via Beta(1,1) prior under H1."""
    n_d = b + c
    if n_d == 0:
        return 1.0
    from math import comb as C
    integral = sum(C(n_d, b) * (p / 1000) ** b * (1 - p / 1000) ** c for p in range(1, 1000)) / 999
    marg_h0 = C(n_d, b) * 0.5 ** n_d
    return integral / marg_h0 if marg_h0 > 0 else 1.0


def bootstrap_ci(data: Sequence[float], n_boot: int = 10000, ci: float = 0.95, seed: int = 42):
    """Non-parametric bootstrap CI on the mean."""
    import random
    rng = random.Random(seed)
    n = len(data)
    if n == 0:
        return (0.0, 0.0)
    means = [sum(data[rng.randrange(n)] for _ in range(n)) / n for _ in range(n_boot)]
    means.sort()
    return (means[int((1 - ci) / 2 * n_boot)], means[int((1 + ci) / 2 * n_boot)])


def bh_correction(pvals: Iterable[float], alpha: float = 0.05) -> list[dict]:
    """Benjamini-Hochberg. Returns per-hypothesis decision records."""
    pvals = list(pvals)
    n = len(pvals)
    order = sorted(range(n), key=lambda i: pvals[i])
    out = []
    for rank, i in enumerate(order, 1):
        thr = rank / n * alpha
        out.append({"index": i, "p": pvals[i], "rank": rank, "threshold": thr,
                    "reject_null": pvals[i] <= thr})
    return out
