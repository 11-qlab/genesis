"""Opt-in real-provider regression test.

Runs only when the environment is configured:

    export AGI_TEST_PROVIDER_URL=https://api.groq.com/openai/v1
    export AGI_TEST_PROVIDER_MODEL=openai/gpt-oss-120b
    export AGI_TEST_PROVIDER_KEY_ENV=AGI_API_KEY
    export AGI_API_KEY=sk-...
    pytest -m network tests/integration/test_provider_live.py

Without that env, every test here is skipped. `scripts/verify.sh` never
sets `-m network`, so this file is inert during normal verification.

The test exercises `probe()` — the same entrypoint `agi provider probe`
uses — so a failure here is reproducible from the CLI.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from agi.core.config import ProviderConfig
from agi.evaluation import Benchmark, EvalRunner
from agi.providers.openai_compat import OpenAICompatProvider
from agi.providers.probe import probe
from agi.storage import Store
from agi.tools import build_registry

pytestmark = pytest.mark.network

BENCH_FS = Path(__file__).resolve().parents[2] / "bench" / "workspace_list.jsonl"
BENCH_MEM = Path(__file__).resolve().parents[2] / "bench" / "memory_search.jsonl"


def _live_config() -> ProviderConfig | None:
    url = os.environ.get("AGI_TEST_PROVIDER_URL")
    model = os.environ.get("AGI_TEST_PROVIDER_MODEL")
    key_env = os.environ.get("AGI_TEST_PROVIDER_KEY_ENV", "AGI_API_KEY")
    if not url or not model or not os.environ.get(key_env):
        return None
    return ProviderConfig(
        kind="openai_compat",
        name="live",
        base_url=url,
        model=model,
        api_key_env=key_env,
        timeout_s=60.0,
        max_retries=1,
    )


@pytest.fixture(scope="module")
def live_cfg() -> ProviderConfig:
    cfg = _live_config()
    if cfg is None:
        pytest.skip("live provider not configured")
    return cfg


def test_live_probe_complete(live_cfg: ProviderConfig) -> None:
    report = probe(live_cfg)
    assert report.overall_ok, report.as_dict()
    assert report.checks["complete"].get("ok") is True


def test_live_workspace_benchmark(live_cfg: ProviderConfig, tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    store = Store(tmp_path / "e.sqlite3")
    try:
        provider = OpenAICompatProvider(
            name=live_cfg.name,
            base_url=live_cfg.base_url,
            model=live_cfg.model,
            api_key_env=live_cfg.api_key_env,
            timeout_s=live_cfg.timeout_s,
            max_retries=live_cfg.max_retries,
        )
        tools = build_registry(["fs_list"], str(ws))
        bench = Benchmark.from_file(BENCH_FS)
        result = EvalRunner(
            provider=provider, tools=tools, store=store,
            runtime=_runtime_for_eval(),
        ).run(bench)
        assert result.accuracy >= 0.67, (
            f"real model accuracy dropped to {result.accuracy:.2f} on "
            f"{bench.name} — inspect per-item failures"
        )
    finally:
        store.close()


def _runtime_for_eval():
    from agi.core import load_config
    return load_config()


# Skip the memory benchmark by default — it requires --seed memory plumbing
# that lives in the CLI, not the library. Reproduce with:
#   AGI_TEST_PROVIDER_URL=... AGI_TEST_PROVIDER_MODEL=... \
#   pytest -m network tests/integration/test_provider_live.py::test_live_workspace_benchmark
