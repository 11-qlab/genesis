#!/usr/bin/env python3
"""F4 diagnostic — run CalibrationProbe on each error_recovery item.

Distinguishes:
  CASE 1: raw_text == "50" for every item      → model truly degenerate
  CASE 2: raw_text is non-numeric / parse fails → probe fallback, harness bug
  CASE 3: mixed                                 → weak real signal

Requires the same env vars as `agi eval run`: AGI_PROVIDER_KIND,
AGI_BASE_URL, AGI_MODEL, and either AGI_API_KEYS or AGI_API_KEY.
"""
from __future__ import annotations

import os
import sys
import time

# Allow `python3 scripts/diagnose_calibration_parse.py` from the repo root.
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "src"))

from agi.core import load_config  # noqa: E402
from agi.evaluation.dataset import load_dataset  # noqa: E402
from agi.providers.router import build_provider  # noqa: E402
from agi.reasoning.planner import Planner  # noqa: E402
from agi.trajectories import CalibrationProbe  # noqa: E402
from agi.tools import build_registry  # noqa: E402


def main() -> int:
    cfg = load_config()
    provider = build_provider(cfg.provider)
    catalog = build_registry(
        cfg.tools.enabled, cfg.tools.fs_root,
        shell_enabled=cfg.tools.shell_enabled,
    ).describe()

    dataset = load_dataset(os.path.join(REPO, "bench", "error_recovery.jsonl"))
    probe = CalibrationProbe(provider)
    planner = Planner(provider, catalog)

    print(f"{'item_id':12s} {'est':>4s} {'ok':>4s}  {'raw_text':60s}")
    print("-" * 90)
    rows: list[tuple[str, int | None, bool | None]] = []
    for item in dataset:
        try:
            plan = planner.plan(item.goal, temperature=0.0)
        except Exception as exc:
            print(f"{item.id:12s} {'---':>4s} {'---':>4s}  plan error: {exc}")
            continue
        try:
            est = probe.estimate(item.goal, plan, catalog)
        except Exception as exc:
            print(f"{item.id:12s} {'---':>4s} {'---':>4s}  probe error: {exc}")
            continue
        raw = (probe.last_raw_text or "").replace("\n", " ")[:58] or "(empty)"
        ok = probe.last_parsed_ok
        rows.append((item.id, est, ok))
        print(f"{item.id:12s} {est:>4d} {str(ok):>4s}  {raw!r}")
        time.sleep(0.3)

    print()
    parsed_ok = sum(1 for _, _, ok in rows if ok)
    total = len(rows)
    print(f"parsed_ok: {parsed_ok}/{total}")

    if total == 0:
        print("CASE 0: no probe results — all plan or probe calls failed.")
        return 2

    all_ok = parsed_ok == total
    all_est_50 = all(est == 50 for _, est, _ in rows)
    all_fail = parsed_ok == 0

    if all_ok and all_est_50:
        print("CASE 1: model returns 50 for every probe. T8 truly degenerate.")
        return 0
    if all_fail:
        print("CASE 2: probe fallback fires for every item. T8 is NOT measured.")
        print("        Harness bug: CalibrationProbe cannot parse the model's reply.")
        return 0
    print("CASE 3: mixed results — estimates vary or parses partly succeed.")
    print("        T8 has weak signal. Characterize with multi-run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
