from __future__ import annotations

from pathlib import Path

from agi.core import load_config
from agi.evaluation import Benchmark, EvalRunner, compute_metrics
from agi.providers import EchoProvider
from agi.storage import Store
from agi.tools import build_registry

BENCH = Path(__file__).resolve().parents[2] / "bench" / "workspace_list.jsonl"


def test_bundled_bench_against_echo(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    cfg = load_config()
    provider = EchoProvider()
    tools = build_registry(["fs_list"], str(ws))
    store = Store(tmp_path / "e.sqlite3")
    try:
        bench = Benchmark.from_file(BENCH)
        runner = EvalRunner(provider=provider, tools=tools,
                            store=store, runtime=cfg)
        result = runner.run(bench)
        assert result.total == 3
        assert result.passed == 3
        assert result.accuracy == 1.0
        m = compute_metrics(result)
        assert m.unique_tools == ("fs_list",)

        saved = store.get_eval_run(result.eval_run_id)
        assert saved is not None
        assert saved["status"] == "completed"
        assert saved["passed"] == 3
        items = store.list_eval_items(result.eval_run_id)
        assert len(items) == 3
        assert all(item["passed"] == 1 for item in items)
    finally:
        store.close()
