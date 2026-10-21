from __future__ import annotations

from agi.core.config import ProviderConfig
from agi.providers.probe import probe


def test_echo_probe_ok() -> None:
    cfg = ProviderConfig(kind="echo", name="echo")
    report = probe(cfg)
    assert report.overall_ok is True
    assert report.checks["health"]["ok"] is True
    assert report.checks["complete"]["ok"] is True


def test_openai_probe_without_server_fails_cleanly() -> None:
    cfg = ProviderConfig(
        kind="openai_compat",
        name="unreachable",
        base_url="http://127.0.0.1:1/v1",  # nothing there
        model="m",
        api_key_env="AGI_TEST_PROBE_KEY",
        timeout_s=2.0,
        max_retries=0,
    )
    report = probe(cfg)
    assert report.overall_ok is False
    assert "complete" in report.checks
    assert report.checks["complete"]["ok"] is False
    assert "credential_present" in report.as_dict()
