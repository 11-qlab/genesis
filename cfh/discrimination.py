"""A/B discrimination probe with position control."""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Optional

from .llm import LLMClient
from .types import Trajectory


def _extract_letter(text: str) -> str | None:
    """Extract 'A' or 'B' from a possibly-long reply.

    Strategy: prefer a leading A/B; otherwise the last standalone A/B in the
    text; otherwise None.
    """
    t = text.strip()
    if not t:
        return None
    if t[0] in ("A", "B"):
        # Must be followed by non-alnum (space, punctuation, end)
        if len(t) == 1 or not t[1].isalnum():
            return t[0]
    # Scan for standalone A/B tokens
    import re as _re
    matches = _re.findall(r"\b([AB])\b", t)
    if matches:
        return matches[-1]  # last one — reasoning models conclude
    return None


PROBE_SYSTEM = (
    "You are an expert agent auditor. You will be shown a goal and two "
    "candidate trajectories (A and B). Decide which trajectory achieves the "
    "goal using tools correctly.\n\n"
    "RULES:\n"
    "- Your ENTIRE reply must be a single character: A or B.\n"
    "- Do not explain. Do not reason. Do not add punctuation or whitespace.\n"
    "- Answer with A or B as the first character of your reply."
)


def _render_traj(t: Trajectory, max_steps: int = 20) -> str:
    lines = []
    for i, s in enumerate(t.steps[:max_steps]):
        if s.tool_call:
            lines.append(f"  {i}. CALL {s.tool_call.short(120)}")
        elif s.observation is not None:
            obs = s.observation if len(s.observation) < 200 else s.observation[:200] + "..."
            lines.append(f"  {i}. OBS  {obs}")
        else:
            c = s.content if len(s.content) < 200 else s.content[:200] + "..."
            lines.append(f"  {i}. SAY  {c}")
    return "\n".join(lines)


@dataclass
class ProbeResult:
    pair_id: str
    a_id: str
    b_id: str
    goal: str
    a_outcome: str
    b_outcome: str
    label: str
    p_a: float
    p_b: float
    entropy: float
    n_samples: int
    raw: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def correct(self, ground_truth: str) -> Optional[bool]:
        if self.label == "undecided":
            return None
        return self.label == ground_truth

    @property
    def confidence(self) -> float:
        return max(self.p_a, self.p_b)


class DiscriminationProbe:
    def __init__(self, llm: LLMClient, n_samples: int = 5,
                 use_logprobs: bool = True, max_steps: int = 20) -> None:
        self.llm = llm
        self.n_samples = n_samples
        self.use_logprobs = use_logprobs
        self.max_steps = max_steps

    def _build_prompt(self, goal, a, b):
        user = (
            f"GOAL: {goal}\n\n"
            f"TRAJECTORY A:\n{_render_traj(a, self.max_steps)}\n\n"
            f"TRAJECTORY B:\n{_render_traj(b, self.max_steps)}\n\n"
            "Which trajectory achieves the goal? Answer A or B."
        )
        return [{"role": "system", "content": PROBE_SYSTEM},
                {"role": "user", "content": user}]

    def _score_once(self, messages):
        if self.use_logprobs:
            try:
                _, ts = self.llm.complete_with_logprobs(messages, max_tokens=512)
                if ts is not None:
                    la = ts.for_token("A")
                    lb = ts.for_token("B")
                    if la is not None and lb is not None:
                        m = max(la, lb)
                        ea, eb = math.exp(la - m), math.exp(lb - m)
                        s = ea + eb
                        return ea / s, eb / s, "A" if ea >= eb else "B"
            except Exception:
                pass
        votes = {"A": 0, "B": 0, "undecided": 0}
        for _ in range(self.n_samples):
            txt = self.llm.complete(
                messages, temperature=0.2, max_tokens=256,
            ).strip().upper()
            # Reasoning models put the answer at the end of CoT, not the start.
            # Scan the whole reply for standalone A/B letters.
            letter = _extract_letter(txt)
            if letter == "A":
                votes["A"] += 1
            elif letter == "B":
                votes["B"] += 1
            else:
                votes["undecided"] += 1
        n = sum(votes.values()) or 1
        pa, pb = votes["A"] / n, votes["B"] / n
        label = "A" if pa > pb else ("B" if pb > pa else "undecided")
        return pa, pb, label

    def score_pair(self, goal, a, b, pair_id=""):
        pair_id = pair_id or f"{a.traj_id}__{b.traj_id}"
        fwd = self._build_prompt(goal, a, b)
        fa, fb, _ = self._score_once(fwd)
        rev = self._build_prompt(goal, b, a)
        ra, rb, _ = self._score_once(rev)
        p_a = 0.5 * (fa + rb)
        p_b = 0.5 * (fb + ra)
        s = p_a + p_b
        if s > 0:
            p_a, p_b = p_a / s, p_b / s
        label = "A" if p_a > p_b + 1e-6 else ("B" if p_b > p_a + 1e-6 else "undecided")
        h = 0.0
        for p in (p_a, p_b):
            if p > 0:
                h -= p * math.log2(p)
        return ProbeResult(
            pair_id=pair_id, a_id=a.traj_id, b_id=b.traj_id, goal=goal,
            a_outcome=a.outcome, b_outcome=b.outcome, label=label,
            p_a=p_a, p_b=p_b, entropy=h, n_samples=self.n_samples, raw=[],
        )

    def batch(self, pairs):
        results = []
        for i, (a, b) in enumerate(pairs):
            goal = a.goal or b.goal
            results.append(self.score_pair(goal, a, b, pair_id=f"pair_{i:04d}"))
        return results
