from __future__ import annotations

from agi.providers.base import Completion, Message
from agi.reasoning import Plan, PlanStep
from agi.trajectories import (
    CalibrationProbe,
    brier_score,
    expected_calibration_error,
)
from agi.trajectories.t8_calibration import CalibrationSample


class _FixedText:
    name = "fixed"
    model = "m"

    def __init__(self, text: str) -> None:
        self._text = text

    def complete(self, messages: list[Message], **_kw) -> Completion:
        return Completion(text=self._text, model=self.model)

    def stream(self, messages: list[Message], **_kw):
        yield self.complete(messages).text

    def health(self) -> dict:
        return {"ok": True}


def _plan() -> Plan:
    return Plan(goal="g", steps=[
        PlanStep(id="s1", title="t", tool="fs_list", args={"path": "."}),
    ])


def test_estimate_parses_integer():
    probe = CalibrationProbe(_FixedText("75"))
    assert probe.estimate("g", _plan(), [{"name": "fs_list"}]) == 75


def test_estimate_clamps_high():
    probe = CalibrationProbe(_FixedText("150"))
    assert probe.estimate("g", _plan(), []) == 100


def test_estimate_default_on_garbage():
    probe = CalibrationProbe(_FixedText("no number here"))
    assert probe.estimate("g", _plan(), []) == 50


def test_estimate_extracts_from_chatty_text():
    probe = CalibrationProbe(_FixedText("I think about 40 percent"))
    assert probe.estimate("g", _plan(), []) == 40


def test_brier_perfect():
    samples = [
        CalibrationSample("g", estimate=100, actual_success=True),
        CalibrationSample("g", estimate=0, actual_success=False),
    ]
    assert brier_score(samples) == 0.0


def test_brier_always_half():
    samples = [
        CalibrationSample("g", estimate=50, actual_success=True),
        CalibrationSample("g", estimate=50, actual_success=False),
    ]
    assert abs(brier_score(samples) - 0.25) < 1e-9


def test_ece_perfect():
    samples = [
        CalibrationSample("g", estimate=100, actual_success=True),
        CalibrationSample("g", estimate=0, actual_success=False),
    ]
    assert expected_calibration_error(samples) == 0.0


def test_ece_poorly_calibrated():
    """Model says 100% but always fails → ECE ~= 1.0 in the last bucket."""
    samples = [
        CalibrationSample("g", estimate=100, actual_success=False),
        CalibrationSample("g", estimate=100, actual_success=False),
        CalibrationSample("g", estimate=100, actual_success=False),
    ]
    ece = expected_calibration_error(samples)
    assert abs(ece - 1.0) < 1e-9
