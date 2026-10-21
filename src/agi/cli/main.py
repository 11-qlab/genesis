"""The `agi` command-line interface."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .. import __version__
from ..agents.simple import SimpleAgent
from ..core.config import AppConfig, load_config
from ..core.errors import AGIError
from ..core.logging import setup_logging
from ..observability.health import collect_health, environment_info
from ..providers.base import Message
from ..providers.router import ProviderRouter, build_provider
from ..reasoning.planner import Planner
from ..storage.sqlite import Store
from ..tools import build_registry
from ..tools.registry import ToolRegistry

app = typer.Typer(no_args_is_help=True, help="AGI research platform CLI.")
config_app = typer.Typer(help="Configuration helpers.")
app.add_typer(config_app, name="config")

console = Console()


def _boot() -> tuple[AppConfig, ProviderRouter, ToolRegistry, Store]:
    cfg = load_config()
    setup_logging(cfg.runtime.log_level, cfg.runtime.log_json)
    Path(cfg.tools.fs_root).mkdir(parents=True, exist_ok=True)
    provider = build_provider(cfg.provider)
    router = ProviderRouter(default=provider)
    tools = build_registry(
        cfg.tools.enabled,
        cfg.tools.fs_root,
        shell_enabled=cfg.tools.shell_enabled,
        shell_allowlist=cfg.tools.shell_allowlist,
        shell_timeout_s=cfg.tools.shell_timeout_s,
    )
    store = Store(cfg.storage.path)
    # Memory is wired in after the registry so `tools/` keeps its dependency
    # footprint. Available to the planner only because it's registered here.
    try:
        from ..memory import MemorySearchTool, Retriever

        tools.register(MemorySearchTool(Retriever(store, _build_embedder(cfg))))
    except Exception:  # pragma: no cover - numpy missing, import error, etc.
        # `memory_search` is optional; without it the registry is still usable.
        pass
    return cfg, router, tools, store


def _json(value) -> None:
    typer.echo(json.dumps(value, indent=2, default=str))


def _build_embedder(cfg):
    """Build the embedding provider for memory.

    `AGI_EMBEDDING_KIND` controls the choice:
      - "hash" (default): offline, deterministic, works everywhere
      - "openai_compat": use the provider's base_url + model + key
    Most chat providers do not expose /embeddings; the default is hash so the
    memory feature works out of the box against any endpoint.
    """
    import os

    from ..memory import build_embedding

    kind = os.environ.get("AGI_EMBEDDING_KIND", "hash").lower()
    if kind == "openai_compat":
        return build_embedding(
            "openai_compat",
            base_url=cfg.provider.base_url,
            model=cfg.provider.model,
            api_key_env=cfg.provider.api_key_env,
        )
    if kind != "hash":
        raise SystemExit(
            f"unknown AGI_EMBEDDING_KIND: {kind!r} (expected 'hash' or 'openai_compat')"
        )
    return build_embedding("hash", dim=256)


@app.command()
def version() -> None:
    """Print the CLI version."""
    typer.echo(f"agi {__version__}")


@app.command()
def doctor() -> None:
    """Diagnostics: python, config, provider, tools, storage path."""
    cfg = load_config()
    _json({
        "environment": environment_info(),
        "config_source": cfg.source,
        "provider": {
            "name": cfg.provider.name,
            "kind": cfg.provider.kind,
            "model": cfg.provider.model,
            "base_url": cfg.provider.base_url,
            "timeout_s": cfg.provider.timeout_s,
        },
        "storage": {"path": cfg.storage.path},
        "tools": {
            "enabled": cfg.tools.enabled,
            "fs_root": cfg.tools.fs_root,
            "shell_enabled": cfg.tools.shell_enabled,
        },
    })


provider_app = typer.Typer(help="Provider inspection commands.")
app.add_typer(provider_app, name="provider")


@provider_app.command("probe")
def provider_probe() -> None:
    """Probe the configured provider: models, complete, stream, embeddings."""
    from ..providers.probe import probe

    cfg = load_config()
    report = probe(cfg.provider)
    _json(report.as_dict())
    if not report.overall_ok:
        raise typer.Exit(code=1)


@app.command()
def health() -> None:
    """Full health snapshot; exit 1 if providers are unhealthy."""
    cfg, router, tools, store = _boot()
    try:
        payload = collect_health(cfg, router, tools, store)
    finally:
        store.close()
    _json(payload)
    if not payload["provider_ok"]:
        raise typer.Exit(code=1)


@config_app.command("show")
def config_show() -> None:
    """Show the resolved configuration."""
    cfg = load_config()
    _json(cfg.model_dump())


@app.command()
def tools() -> None:
    """List registered tools and their argument schemas."""
    _, _, registry, store = _boot()
    try:
        table = Table("name", "description")
        for item in registry.describe():
            table.add_row(item["name"], item["description"])
        console.print(table)
        _json({"schemas": registry.describe()})
    finally:
        store.close()


@app.command()
def chat(
    prompt: str,
    stream: bool = typer.Option(False, "--stream"),
    provider: str = typer.Option(None, "--provider"),
) -> None:
    """One-shot chat with the active provider."""
    _, router, _, store = _boot()
    try:
        target = router.get(provider)
        messages = [Message(role="user", content=prompt)]
        try:
            if stream:
                parts: list[str] = []
                for chunk in target.stream(messages):
                    parts.append(chunk)
                    typer.echo(chunk, nl=False)
                typer.echo()
                _json({"provider": target.name, "mode": "stream",
                       "chars": sum(len(p) for p in parts)})
            else:
                completion = target.complete(messages)
                typer.echo(completion.text)
                _json({
                    "provider": target.name,
                    "model": completion.model,
                    "usage": {
                        "prompt_tokens": completion.usage.prompt_tokens,
                        "completion_tokens": completion.usage.completion_tokens,
                    },
                    "finish_reason": completion.finish_reason,
                })
        except AGIError as exc:
            typer.echo(f"chat failed: {exc}", err=True)
            raise typer.Exit(code=1) from exc
    finally:
        store.close()


repl_app = typer.Typer(
    help="Interactive multi-turn REPL with tool execution.",
    invoke_without_command=True,
)
app.add_typer(repl_app, name="repl")


def _run_repl(
    *,
    max_turns: int,
    summarize: bool,
    show_runs: bool,
) -> None:
    from ..agents.conversation import Conversation

    cfg, router, registry, store = _boot()
    try:
        conv = Conversation(
            provider=router.get(),
            tools=registry,
            store=store,
            runtime=cfg.runtime,
            max_turns=max_turns,
            summarize=summarize,
        )
        typer.echo(
            "agi repl — type a message, or `:help` for commands, `:quit` to exit."
        )
        while True:
            try:
                line = input("\n>> ").strip()
            except (EOFError, KeyboardInterrupt):
                typer.echo("")
                break
            if not line:
                continue
            if line in (":quit", ":q", ":exit"):
                break
            if line == ":help":
                typer.echo(
                    ":help    show this message\n"
                    ":clear   clear conversation history\n"
                    ":history print prior turns\n"
                    ":quit    exit"
                )
                continue
            if line == ":clear":
                conv.clear()
                typer.echo("(history cleared)")
                continue
            if line == ":history":
                if not conv.history:
                    typer.echo("(no turns yet)")
                else:
                    for i, turn in enumerate(conv.history, 1):
                        tools = ", ".join(turn.tool_sequence) or "(no tool)"
                        typer.echo(
                            f"[{i}] {turn.status} | {tools} | "
                            f"{turn.user[:80]!r}"
                        )
                continue
            turn = conv.run_turn(line)
            typer.echo(f"\n{turn.summary}")
            if show_runs and turn.run_id is not None:
                typer.echo(
                    f"  (run {turn.run_id}, {turn.status}, "
                    f"{len(turn.results)} step(s))"
                )
    finally:
        store.close()


@repl_app.callback()
def _repl_callback(
    ctx: typer.Context,
    max_turns: int = typer.Option(20, "--max-turns", min=1, max=200),
    summarize: bool = typer.Option(True, "--summarize/--raw"),
    show_runs: bool = typer.Option(False, "--show-runs/--quiet-runs"),
) -> None:
    """Start the interactive REPL. Use `agi repl once "<goal>"` for one turn."""
    if ctx.invoked_subcommand is not None:
        return
    _run_repl(max_turns=max_turns, summarize=summarize, show_runs=show_runs)


@repl_app.command("once")
def repl_once(
    prompt: str,
    summarize: bool = typer.Option(True, "--summarize/--raw"),
) -> None:
    """Run one turn through the same machinery, then exit."""
    from ..agents.conversation import Conversation

    cfg, router, registry, store = _boot()
    try:
        conv = Conversation(
            provider=router.get(),
            tools=registry,
            store=store,
            runtime=cfg.runtime,
            summarize=summarize,
        )
        turn = conv.run_turn(prompt)
        typer.echo(turn.summary)
        if turn.run_id is not None:
            typer.echo(
                f"  (run {turn.run_id}, {turn.status}, "
                f"{len(turn.results)} step(s))"
            )
    finally:
        store.close()


@app.command()
def plan(goal: str) -> None:
    """Ask the planner for a validated plan; do not execute it."""
    _, router, registry, store = _boot()
    try:
        planner = Planner(router.get(), registry.describe())
        try:
            result = planner.plan(goal)
        except AGIError as exc:
            typer.echo(f"plan failed: {exc}", err=True)
            raise typer.Exit(code=1) from exc
        _json(result.model_dump())
    finally:
        store.close()


@app.command()
def run(goal: str) -> None:
    """Plan and execute a goal end-to-end, recording all events."""
    cfg, router, registry, store = _boot()
    try:
        agent = SimpleAgent(router.get(), registry, store, cfg.runtime)
        try:
            result = agent.execute(goal)
        except AGIError as exc:
            typer.echo(f"run failed: {exc}", err=True)
            raise typer.Exit(code=1) from exc
        _json(result)
    finally:
        store.close()


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8000, "--port", min=1, max=65535),
    allow_remote: bool = typer.Option(False, "--allow-remote"),
) -> None:
    """Run the loopback HTTP API."""
    from ..api.server import serve as _serve

    if host not in {"127.0.0.1", "::1", "localhost"} and not allow_remote:
        typer.echo(
            f"refusing to bind non-loopback host {host!r} without --allow-remote",
            err=True,
        )
        raise typer.Exit(code=2)
    cfg, router, registry, store = _boot()
    typer.echo(f"agi api listening on http://{host}:{port}")
    try:
        _serve(cfg, router, registry, store, host=host, port=port)
    finally:
        store.close()


memory_app = typer.Typer(help="Document memory commands.")
app.add_typer(memory_app, name="memory")


def _make_embedder(cfg):
    return _build_embedder(cfg)


@memory_app.command("ingest")
def memory_ingest(path: str) -> None:
    """Ingest a UTF-8 text file into the document store."""
    from ..memory import MemoryError, Retriever

    cfg, _router, _tools, store = _boot()
    try:
        retriever = Retriever(store, _make_embedder(cfg))
        try:
            doc, n = retriever.ingest_file(path)
        except MemoryError as exc:
            typer.echo(f"ingest failed: {exc}", err=True)
            raise typer.Exit(code=1) from exc
        _json({"document_id": doc.id, "title": doc.title, "chunks": n,
               "status": "ingested" if n else "already present"})
    finally:
        store.close()


@memory_app.command("search")
def memory_search(
    query: str,
    k: int = typer.Option(5, "-k", "--top-k", min=1, max=50),
) -> None:
    """Search ingested chunks for the closest matches."""
    from ..memory import MemoryError, Retriever

    cfg, _router, _tools, store = _boot()
    try:
        retriever = Retriever(store, _make_embedder(cfg))
        try:
            hits = retriever.search(query, k=k)
        except MemoryError as exc:
            typer.echo(f"search failed: {exc}", err=True)
            raise typer.Exit(code=1) from exc
        _json({
            "query": query,
            "hits": [
                {
                    "document_id": h.document_id,
                    "chunk_index": h.chunk_index,
                    "score": round(h.score, 6),
                    "text": h.text[:200],
                }
                for h in hits
            ],
        })
    finally:
        store.close()


@memory_app.command("list")
def memory_list() -> None:
    """List ingested documents."""
    _, _, _, store = _boot()
    try:
        table = Table("id", "title", "source")
        for row in store.list_memory_documents():
            table.add_row(row["id"], row["title"], row["source"])
        console.print(table)
    finally:
        store.close()


eval_app = typer.Typer(help="Evaluation commands.")
app.add_typer(eval_app, name="eval")


@eval_app.command("run")
def eval_run(
    bench: str = typer.Option("bench/workspace_list.jsonl", "--bench"),
    markdown: bool = typer.Option(False, "--markdown"),
    seed: str = typer.Option(
        "none",
        "--seed",
        help=(
            "Per-item seeding strategy: none | memory | files | all. "
            "`memory` ingests item.raw.seed_documents into the memory store. "
            "`files` writes item.raw.seed_files into AGI_FS_ROOT. "
            "`all` does both."
        ),
    ),
    delay_ms: int = typer.Option(
        0, "--delay-ms",
        help="Sleep this many ms between items (rate-limit pacing).",
        min=0, max=60000,
    ),
    typed_plans: bool = typer.Option(
        False, "--typed-plans/--no-typed-plans",
        help="Enable static type checking + type-directed repair of plans.",
    ),
    strategy: str = typer.Option(
        "greedy", "--strategy",
        help="Plan strategy: greedy | self-consistent | calibration.",
    ),
    k: int = typer.Option(
        5, "--k", min=1, max=20,
        help="Sample count for --strategy self-consistent.",
    ),
    calibration_bins: int = typer.Option(
        5, "--calibration-bins", min=2, max=20,
        help="Binning for ECE under --strategy calibration.",
    ),
    revision_signal: str = typer.Option(
        "basic", "--revision-signal",
        help="Revision prompt style: basic | rich.",
    ),
) -> None:
    """Execute a benchmark and store the results."""
    import dataclasses

    from ..evaluation import Benchmark, EvalRunner, to_json, to_markdown

    if strategy not in ("greedy", "self-consistent", "calibration", "revision"):
        typer.echo(
            f"unknown --strategy: {strategy!r} "
            "(expected greedy | self-consistent | calibration)",
            err=True,
        )
        raise typer.Exit(code=2)

    cfg, router, registry, store = _boot()
    try:
        try:
            benchmark = Benchmark.from_file(bench)
        except Exception as exc:
            typer.echo(f"cannot load benchmark: {exc}", err=True)
            raise typer.Exit(code=2) from exc

        if seed not in ("none", "memory", "files", "all"):
            typer.echo(f"unknown --seed value: {seed!r}", err=True)
            raise typer.Exit(code=2)

        seed_memory = seed in ("memory", "all")
        seed_files = seed in ("files", "all")

        if seed_memory or seed_files:
            retriever = None
            if seed_memory:
                from ..memory import Retriever

                retriever = Retriever(store, _build_embedder(cfg))

            def _seed(item) -> None:
                if seed_memory:
                    from ..memory import Document, MemoryError

                    for spec in item.raw.get("seed_documents") or []:
                        source = spec.get("source")
                        text = spec.get("text")
                        if not source or not text:
                            raise MemoryError(
                                f"item {item.id}: seed_documents entries need source+text"
                            )
                        retriever.ingest_document(Document.from_text(source, text))
                if seed_files:
                    import pathlib

                    root = pathlib.Path(cfg.tools.fs_root)
                    root.mkdir(parents=True, exist_ok=True)
                    for rel_path, content in (item.raw.get("seed_files") or {}).items():
                        target = root / rel_path
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_text(content, encoding="utf-8")

            benchmark = dataclasses.replace(benchmark, before_each=_seed)

        runner = EvalRunner(
            provider=router.get(),
            tools=registry,
            store=store,
            runtime=cfg,
            delay_ms=delay_ms,
            enable_typed_plans=typed_plans,
            strategy=strategy,
            self_consistency_k=k,
            calibration_bins=calibration_bins,
            revision_signal=revision_signal,
        )
        result = runner.run(benchmark)
    finally:
        store.close()
    if result.contaminated:
        typer.echo(
            f"CONTAMINATED: {result.rate_limited_items}/{result.total} items "
            f"failed with rate-limit or billing errors. Discard this run.",
            err=True,
        )

    if markdown:
        typer.echo(to_markdown(result))
    else:
        typer.echo(to_json(result))

    if result.contaminated:
        raise typer.Exit(code=3)  # distinct from accuracy failure
    if result.accuracy < 1.0:
        raise typer.Exit(code=1)


@eval_app.command("compare")
def eval_compare(
    a_id: int = typer.Argument(...),
    b_id: int = typer.Argument(...),
    markdown: bool = typer.Option(False, "--markdown"),
) -> None:
    """Compare two stored evaluation runs (read-only, no execution)."""
    from ..evaluation.compare import (
        CompareError,
        compare_runs,
        format_compare_json,
        format_compare_markdown,
    )

    _, _, _, store = _boot()
    try:
        try:
            result = compare_runs(store, a_id, b_id)
        except CompareError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=1) from exc
    finally:
        store.close()

    if markdown:
        typer.echo(format_compare_markdown(result))
    else:
        typer.echo(format_compare_json(result))


@eval_app.command("explain")
def eval_explain(eval_run_id: int) -> None:
    """Interpret a stored eval run: what it proves and what it does not."""
    from ..evaluation.explain import explain_run, format_explain

    _, _, _, store = _boot()
    try:
        try:
            result = explain_run(store, eval_run_id)
        except ValueError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=1) from exc
    finally:
        store.close()
    typer.echo(format_explain(result))


@eval_app.command("list")
def eval_list(limit: int = typer.Option(20, "--limit")) -> None:
    """List recent evaluation runs."""
    _, _, _, store = _boot()
    try:
        table = Table("id", "benchmark", "provider", "model", "acc", "total", "status")
        for row in store.list_eval_runs(limit):
            table.add_row(
                str(row["id"]), row["benchmark"], row["provider"], row["model"],
                f"{row['accuracy']:.2f}", str(row["total"]), row["status"],
            )
        console.print(table)
    finally:
        store.close()


@eval_app.command("show")
def eval_show(eval_run_id: int, markdown: bool = typer.Option(False, "--markdown")) -> None:
    """Show one evaluation run and its per-item rows."""
    from ..evaluation import (
        EvalResult,
        ItemOutcome,
    )
    from ..evaluation.dataset import DatasetItem
    from ..evaluation.report import to_json, to_markdown

    _, _, _, store = _boot()
    try:
        run = store.get_eval_run(eval_run_id)
        if run is None:
            typer.echo(f"no such eval run: {eval_run_id}", err=True)
            raise typer.Exit(code=1)
        items = store.list_eval_items(eval_run_id)
    finally:
        store.close()

    outcomes = tuple(
        ItemOutcome(
            item=DatasetItem(
                id=r["item_id"], goal=r["goal"],
                expect_tool=r["expect_tool"], expect_status="succeeded",
            ),
            run_status=r["status"],
            tool_used=r["tool_used"],
            duration_ms=r["duration_ms"],
            run_id=r["run_id"],
            passed=bool(r["passed"]),
            detail=r["detail"] or "",
        )
        for r in items
    )
    result = EvalResult(
        benchmark=run["benchmark"], provider=run["provider"], model=run["model"],
        total=run["total"], passed=run["passed"],
        duration_ms=run["duration_ms"], items=outcomes,
        eval_run_id=run["id"],
    )
    if markdown:
        typer.echo(to_markdown(result))
    else:
        typer.echo(to_json(result))


train_app = typer.Typer(help="Training commands (default: no execution).")
app.add_typer(train_app, name="train")


def _print_train_notice() -> None:
    typer.echo(
        "TRAINING IS DISABLED BY DEFAULT. This command only prepares or "
        "estimates unless --yes-train is passed AND the adapter implements run().",
        err=True,
    )


@train_app.command("estimate")
def train_estimate(
    params_b: float = typer.Option(7.0, "--params-b"),
    tokens: int = typer.Option(1_000_000_000, "--tokens"),
    batch_size: int = typer.Option(4, "--batch-size"),
    seq_len: int = typer.Option(2048, "--seq-len"),
    epochs: int = typer.Option(1, "--epochs"),
    seconds_per_step: float = typer.Option(1.5, "--seconds-per-step"),
) -> None:
    """Print a rough resource estimate. Does not touch a dataset."""
    from ..training.estimator import estimate_dict

    _print_train_notice()
    result = estimate_dict(
        params_b=params_b, tokens=tokens, batch_size=batch_size,
        seq_len=seq_len, epochs=epochs, seconds_per_step=seconds_per_step,
    )
    _json(result)


@train_app.command("prepare")
def train_prepare(
    name: str = typer.Option(..., "--name"),
    base_model: str = typer.Option(..., "--base-model"),
    dataset: str = typer.Option(..., "--dataset"),
) -> None:
    """Validate a job spec and record it. No training is started."""
    from ..training.registry import CheckpointRegistry

    _print_train_notice()
    path = Path(dataset)
    if not path.is_file():
        typer.echo(f"dataset not found: {dataset}", err=True)
        raise typer.Exit(code=2)
    summary = {
        "name": name,
        "base_model": base_model,
        "dataset": str(path.resolve()),
        "bytes": path.stat().st_size,
    }
    registry = CheckpointRegistry(Path("checkpoints"))
    _json({"prepared": summary, "checkpoint_index": str(registry.index_path)})


@train_app.command("run")
def train_run(
    name: str = typer.Option(..., "--name"),
    base_model: str = typer.Option(..., "--base-model"),
    dataset: str = typer.Option(..., "--dataset"),
    yes_train: bool = typer.Option(False, "--yes-train"),
) -> None:
    """Start a training job. Requires --yes-train."""
    _print_train_notice()
    if not yes_train:
        typer.echo("refusing to start training without --yes-train", err=True)
        raise typer.Exit(code=2)
    typer.echo(
        "No concrete training adapter is installed. "
        "Build an adapter under src/agi/training/ and register it here.",
        err=True,
    )
    raise typer.Exit(code=2)


@app.command()
def runs(limit: int = typer.Option(20, "--limit")) -> None:
    """List recent runs."""
    _, _, _, store = _boot()
    try:
        table = Table("id", "status", "provider", "model", "goal")
        for row in store.list_runs(limit):
            table.add_row(
                str(row["id"]), row["status"], row["provider"],
                row["model"], (row["goal"] or "")[:60],
            )
        console.print(table)
    finally:
        store.close()


@app.command()
def show(run_id: int) -> None:
    """Show a run's record and its event log."""
    _, _, _, store = _boot()
    try:
        record = store.get_run(run_id)
        if record is None:
            typer.echo(f"no such run: {run_id}", err=True)
            raise typer.Exit(code=1)
        _json({"run": record})
        table = Table("id", "kind", "payload")
        for event in store.list_events(run_id):
            table.add_row(
                str(event["id"]), event["kind"],
                json.dumps(event["payload"], ensure_ascii=False)[:100],
            )
        console.print(table)
    finally:
        store.close()


if __name__ == "__main__":
    app()
