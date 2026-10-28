#!/usr/bin/env python3
"""30_anomaly_report.py — surface failures the taxonomy cannot explain.

Reads autonomous_journal.jsonl + taxonomy.json. Writes state/anomalies.jsonl.
Makes NO claims. Mutates NOTHING. Exit 0 always (unless journal unreadable).

Anomaly kinds:
  skip_generation_failed    experiment_type=skip, reason=generation_failed
                            -> the loop TRIED to generate, failed. Unmet need.
  candidate_invalid         validation.valid == false
                            -> the 4-layer gate rejected a candidate. Reason?
  contaminated_run          result.results[*].infra > result.results[*].valid
                            -> update() would have refused; flag anyway.
  unclassified_class        class not present in taxonomy classes[]
  zero_valid                result.results[*].valid == 0 with no infra
                            -> nothing usable to reason about.
  unknown_experiment_type   experiment_type outside the update() whitelist
"""
import json, sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
JRN  = ROOT / "autonomous_journal.jsonl"
TAX  = ROOT / "taxonomy.json"
OUTD = ROOT / "state"; OUTD.mkdir(exist_ok=True)
OUT  = OUTD / "anomalies.jsonl"

if not JRN.exists(): print(f"ASSUMPTION_BROKEN: {JRN} missing", file=sys.stderr); sys.exit(2)
if not TAX.exists(): print(f"ASSUMPTION_BROKEN: {TAX} missing",  file=sys.stderr); sys.exit(2)

tax = json.loads(TAX.read_text())
known_classes = {c["name"] + "/" + c["subtype"] for c in tax.get("classes", [])}
known_types   = {"held_out", "repeat_trials", "intervention_repeat",
                 "cross_model", "generated_test", "skip"}

anoms, total = [], 0
for i, line in enumerate(JRN.read_text().splitlines(), 1):
    if not line.strip(): continue
    total += 1
    try: ev = json.loads(line)
    except json.JSONDecodeError:
        anoms.append({"line": i, "kind": "unparseable_json", "raw": line[:120]}); continue
    cls  = ev.get("class", "")
    etyp = ev.get("experiment_type", "")
    base = {"line": i, "class": cls, "experiment_type": etyp,
            "timestamp": ev.get("timestamp", "")}

    if etyp not in known_types:
        anoms.append({**base, "kind": "unknown_experiment_type", "value": etyp})

    if cls and cls not in known_classes:
        anoms.append({**base, "kind": "unclassified_class"})

    if etyp == "skip":
        reason = ev.get("reason", "")
        if reason == "generation_failed":
            anoms.append({**base, "kind": "skip_generation_failed",
                          "gap_reason": ev.get("gap", {}).get("reason", "")})
        elif reason == "no plan":
            anoms.append({**base, "kind": "skip_no_plan"})
        continue

    if etyp == "generated_test":
        v = ev.get("validation") or {}
        if v.get("valid") is False:
            anoms.append({**base, "kind": "candidate_invalid",
                          "validation_reason": (v.get("reason") or "")[:120]})
        continue

    res = ev.get("result") or {}
    results = res.get("results") or {}
    if not results:
        anoms.append({**base, "kind": "no_results"}); continue

    for variant, v in results.items():
        valid = v.get("valid", 0); infra = v.get("infra", 0)
        if infra > valid:
            anoms.append({**base, "kind": "contaminated_run",
                          "variant": variant, "valid": valid, "infra": infra})
        elif valid == 0 and infra == 0:
            anoms.append({**base, "kind": "zero_valid", "variant": variant})

with OUT.open("w") as f:
    for a in anoms: f.write(json.dumps(a, sort_keys=True) + "\n")

counts = Counter(a["kind"] for a in anoms)
print(f"journal lines      : {total}")
print(f"anomalies surfaced : {len(anoms)}  -> {OUT}")
print()
for kind, n in counts.most_common():
    print(f"  {kind:<28} {n}")
print()
if any(a["kind"] == "skip_generation_failed" for a in anoms):
    print("[HONEST NOTE] skip_generation_failed means the generator was called and")
    print("              produced no accepted candidate. That IS the current frontier.")
    print("              Do not auto-fix. This is the paper's stated limitation.")
print("[ OK ] next: ./40_paper_numbers.py")
