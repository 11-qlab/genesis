"""T8 — Self-model / calibration.

Kadavath et al. 2022 ("Language Models (Mostly) Know What They Know")
showed that LLMs can be asked to estimate the probability that a
proposed answer is correct ("P(True)"), and that these estimates are
meaningfully correlated with actual correctness on some benchmarks.

This module ports the idea to plan success. Given a goal, a plan, and a
tool catalog:

1. Ask the model: "what is the probability (0-100) that this plan will
   succeed?"
2. Record the estimate alongside the actual outcome.
3. Compute Brier score and expected calibration error (ECE) across a
   set of (estimate, outcome) pairs.

Interpretation of scores:

    Brier: 0 = perfect; 0.25 = always predicting 50%; 1 = perfectly wrong.
    ECE:   0 = perfect; ~0.25 = random; >0.15 = poorly calibrated.

High Brier and ECE mean the model's self-estimate is not useful as a
capability signal. That is a real result, not a failure — it says
self-models at this model size are weak.

Deliberate non-goals: this is not "metacognition". It is a text-in,
text-out probe. The model has no access to its own weights, activations,
or state. Any claim beyond "the estimate correlates with the outcome"
would be overreach.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from ..providers.base import Message, Provider
from ..reasoning.schemas import Plan

_SYSTEM = (
    "You are estimating the probability that a plan will succeed. "
    "Given a goal, a plan (a sequence of tool calls), and the available "
    "tools, estimate the probability (0 to 100) that the plan achieves "
    "the goal without any step failing.\n\n"
    "Reply with a single integer from 0 to 100. No explanation, no "
    "punctuation, no other text."
)

_INT = re.compile(r"\b(\d{1,3})\b")


@dataclass
class CalibrationSample:
    goal: str
    estimate: int       # 0..100
    actual_success: bool


class CalibrationProbe:
    def __init__(self, provider: Provider) -> None:
        self.provider = provider
        # Exposed for F4 diagnostic: raw completion text from the last
        # estimate() call. Distinguishes "model returns 50" from
        # "probe fallback returns 50 because parse failed".
        self.last_raw_text: str | None = None
        self.last_parsed_ok: bool | None = None

    def estimate(
        self,
        goal: str,
        plan: Plan,
        catalog: list[dict[str, Any]],
    ) -> int:
        """Return the model's success estimate (0-100)."""
        payload = {
            "goal": goal,
            "plan": plan.model_dump(),
            "tools": [{"name": t.get("name"), "description": t.get("description")}
                      for t in catalog],
        }
        messages = [
            Message(role="system", content=_SYSTEM),
            Message(role="user", content=json.dumps(payload, indent=2)),
        ]
        # Reasoning models need room to finish their thinking before they
        # emit the number. 16 tokens was cutting off gpt-oss-120b mid-thought
        # (see F4 diagnostic, 2026-10-20). 200 gives plenty of room for the
        # reasoning_content stream, and the answer still lands in `content`.
        completion = self.provider.complete(messages, temperature=0.0, max_tokens=200)
        text = (completion.text or "").strip()
        self.last_raw_text = text
        # Extract first integer 0..100
        m = _INT.search(text)
        if not m:
            self.last_parsed_ok = False
            return 50  # unparseable: fallback (see F4 diagnostic)
        self.last_parsed_ok = True
        n = int(m.group(1))
        return max(0, min(100, n))


def brier_score(samples: list[CalibrationSample]) -> float:
    """Brier score: mean squared difference between estimate and outcome.

    0 = perfect; 0.25 = always predicting 0.5; 1 = perfectly wrong.
    """
    if not samples:
        return 0.0
    total = 0.0
    for s in samples:
        p = s.estimate / 100.0
        y = 1.0 if s.actual_success else 0.0
        total += (p - y) ** 2
    return total / len(samples)


def expected_calibration_error(
    samples: list[CalibrationSample],
    bins: int = 5,
) -> float:
    """Expected calibration error: per-bin |confidence - accuracy|, averaged.

    0 = perfect; ~0.25 = random; >0.15 = poorly calibrated.
    """
    if not samples:
        return 0.0
    buckets: list[list[CalibrationSample]] = [[] for _ in range(bins)]
    for s in samples:
        idx = min(bins - 1, int(s.estimate / 100.0 * bins))
        buckets[idx].append(s)
    total = len(samples)
    ece = 0.0
    for bucket in buckets:
        if not bucket:
            continue
        conf = sum(s.estimate for s in bucket) / len(bucket) / 100.0
        acc = sum(1.0 if s.actual_success else 0.0 for s in bucket) / len(bucket)
        ece += (len(bucket) / total) * abs(conf - acc)
    return ece
