"""Resilient eval wrapper: preflight, checkpoint, retry transport, trajectory."""
from __future__ import annotations
import json, os, subprocess, sys, time
from pathlib import Path

from .health import require_healthy, check_health

ROOT = Path(__file__).resolve().parents[1]
ENV_LOCAL = {
    "PYTHONPATH": "src",
    "AGI_TOOLS_FAMILIES": "1",
}


class ResilientRunner:
    def __init__(self, out_dir: Path, delay_ms: int = 500):
        self.out_dir = out_dir
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.traj_path = out_dir / "trajectories.jsonl"
        self.delay_ms = delay_ms

    def _done_ids(self, checkpoint: Path) -> set[str]:
        if not checkpoint.exists():
            return set()
        done = set()
        for line in checkpoint.read_text().splitlines():
            try:
                done.add(json.loads(line)["item_id"])
            except Exception:
                continue
        return done

    def _run_item(self, bench_file: Path, item_line: str, family: str, tag: str) -> dict:
        """Run one item via agi eval run in a subprocess."""
        tmp_bench = self.out_dir / f"_tmp_{tag}.jsonl"
        tmp_bench.write_text(item_line + "\n")
        db = self.out_dir / f"_db_{tag}.sqlite3"
        ws = self.out_dir / f"_ws_{tag}"
        db.unlink(missing_ok=True)
        if ws.exists():
            for f in ws.rglob("*"):
                f.unlink() if f.is_file() else None
        env = {**os.environ, **ENV_LOCAL,
               "AGI_STORAGE_PATH": str(db), "AGI_FS_ROOT": str(ws)}
        args = [
            sys.executable, "-m", "agi", "eval", "run",
            "--bench", str(tmp_bench),
            "--seed", "all", "--strategy", "greedy",
            "--delay-ms", str(self.delay_ms),
        ]
        try:
            p = subprocess.run(args, cwd=ROOT, env=env,
                               capture_output=True, text=True, timeout=900)
            raw = p.stdout.strip()
            if not raw or not raw.startswith("{"):
                return {"status": "error", "detail": f"no JSON: {p.stderr[:200]}"}
            d = json.loads(raw)
            if not d.get("items"):
                return {"status": "error", "detail": "empty items array"}
            return d["items"][0]
        except subprocess.TimeoutExpired:
            return {"status": "error", "detail": "timeout 900s"}
        except Exception as e:
            return {"status": "error", "detail": f"{type(e).__name__}: {e}"}
        finally:
            tmp_bench.unlink(missing_ok=True)
            db.unlink(missing_ok=True)

    def _is_transport_error(self, item: dict) -> bool:
        detail = (item.get("detail") or "").lower()
        return any(k in detail for k in (
            "errno -3", "errno -2", "temporary failure in name resolution",
            "client error 524", "client error 522", "client error 502",
            "transport error", "urlopen error",
        ))

    def _normalize(self, item: dict, family: str) -> dict:
        seq = item.get("tool_sequence") or []
        steps = [{
            "kind": "assistant", "content": "", "step_index": i,
            "tool_call": {"name": t, "args": {}, "call_id": f"c{i}"},
        } for i, t in enumerate(seq)]
        return {
            "goal": item.get("goal", ""),
            "steps": steps,
            "outcome": "success" if item.get("passed") else "fail",
            "family": family,
            "item_id": item.get("id", ""),
            "duration_ms": item.get("duration_ms", 0),
            "status": item.get("status", "unknown"),
            "detail": item.get("detail", ""),
        }

    def run_bench(self, bench_path: Path, family: str,
                  max_transport_retries: int = 3) -> dict:
        """Run all items, resuming from checkpoint. Returns aggregate."""
        require_healthy()
        checkpoint = Path.home() / ".agi" / "checkpoints" / f"{bench_path.stem}.jsonl"
        checkpoint.parent.mkdir(parents=True, exist_ok=True)

        lines = [l for l in bench_path.read_text().splitlines() if l.strip()]
        done_ids = self._done_ids(checkpoint)
        results: list[dict] = []
        resumed = 0

        # Load existing checkpoint results
        if checkpoint.exists():
            for line in checkpoint.read_text().splitlines():
                try:
                    results.append(json.loads(line))
                except Exception:
                    continue
            resumed = len(results)

        print(f"\n[{family}] {len(lines)} items, {resumed} already done")
        for i, line in enumerate(lines, 1):
            item_raw = json.loads(line)
            item_id = item_raw.get("id", f"item-{i}")
            if item_id in done_ids:
                continue
            for attempt in range(max_transport_retries + 1):
                # Preflight before every item
                if attempt > 0 or (i > 1 and i % 3 == 0):
                    if not check_health(timeout=5).get("ok"):
                        raise SystemExit(
                            f"\nTUNNEL DOWN before {item_id}. State saved in:\n"
                            f"  {checkpoint}\n"
                            f"  {self.traj_path}\n"
                            "Restart tunnel (scripts/infra_up) and rerun to resume."
                        )
                print(f"  [{i}/{len(lines)}] {item_id} (attempt {attempt+1})...", end=" ", flush=True)
                result = self._run_item(bench_path, line, family, f"{family}_{i}")
                if self._is_transport_error(result) and attempt < max_transport_retries:
                    print(f"transport, retry in {2*(attempt+1)}s")
                    time.sleep(2 * (attempt + 1))
                    continue
                break  # got a non-transport result (success or real failure)

            item_result = {
                **result,
                "family": family,
                "item_id": item_id,
                "attempts": attempt + 1,
            }
            results.append(item_result)
            with checkpoint.open("a") as f:
                f.write(json.dumps(item_result) + "\n")
            with self.traj_path.open("a") as f:
                f.write(json.dumps(self._normalize(result, family)) + "\n")
            mark = "✓" if result.get("passed") else "✗"
            dur = result.get("duration_ms", 0) / 1000
            print(f"{mark} {result.get('status','?')} {dur:.1f}s tools={result.get('tool_sequence',[])}")
            if i < len(lines):
                time.sleep(self.delay_ms / 1000.0)

        passed = sum(1 for r in results if r.get("passed"))
        total = len(results)
        return {
            "family": family,
            "total": total,
            "passed": passed,
            "accuracy": passed / total if total else 0.0,
            "results": results,
        }
