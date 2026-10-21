"""Detect contaminated eval runs.

A run is contaminated if >10% of items failed with a rate-limit or
billing error. Contaminated runs must be discarded, not averaged.

See bench/README.md and docs/research/PACING.md.
"""

from __future__ import annotations

_RATE_LIMIT_MARKERS = (
    "429",
    "rate limit",
    "insufficient balance",
    "quota exceeded",
    "402",
)


def is_rate_limited(detail: str) -> bool:
    if not detail:
        return False
    lowered = detail.lower()
    return any(marker in lowered for marker in _RATE_LIMIT_MARKERS)


def classify(details: list[str], threshold: float = 0.10) -> tuple[int, bool]:
    """Return (n_rate_limited, contaminated)."""
    n = sum(1 for d in details if is_rate_limited(d))
    contaminated = len(details) > 0 and (n / len(details)) > threshold
    return n, contaminated
