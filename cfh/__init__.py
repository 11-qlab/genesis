"""Counterfactual Hull Probe (cfh).

Self-adversarial evaluation of capability boundaries in tool-using agents.
"""
from .types import Trajectory, Step, StepKind, ToolCall
from .twins import generate_twins, generate_shortcut_twins
from .discrimination import DiscriminationProbe, ProbeResult
from .metrics import discrimination_score, bootstrap_ci, hull_gap, permutation_test

__all__ = [
    "Trajectory", "Step", "StepKind", "ToolCall",
    "generate_twins", "generate_shortcut_twins",
    "DiscriminationProbe", "ProbeResult",
    "discrimination_score", "bootstrap_ci", "hull_gap", "permutation_test",
]
__version__ = "0.1.0"
