#!/usr/bin/env python3
import json, os, sys, pathlib, re, sys
from collections import Counter, defaultdict
from math import comb
from pathlib import Path

rows = [json.loads(l) for l in Path(str(pathlib.Path(os.environ.get("ARTIFACTS_DIR", "artifacts/traces")) / "planner_traces.jsonl")).read_text().strip().splitlines()]

MARKERS = {
    "template_language": r"template|placeholder|reference|\{\{|\$\{",
    "deferral":          r"output of (step|the read|fs_read)|the contents of|same as|will be substituted",
    "literal_language":  r"literal|exactly|copy|verbatim|actual value",
    "content_word":      r"\bcontent\b",
}
def hits(t):
    t = (t or "").lower()
    return [k for k, pat in MARKERS.items() if re.search(pat, t)]

def fisher(a, an, b, bn):
    n, k = an + bn, a + b
    p = lambda x: comb(an, x) * comb(bn, k - x) / comb(n, k)
    obs = p(a)
    return sum(p(x) for x in range(max(0, k - bn), min(an, k) + 1) if p(x) <= obs)

print(f"{'cond':<10}{'n':<4}{'placeholder':<13}{'literal':<9}{'other':<7}{'mean_rlen'}")
summary = {}
for cond in ("baseline", "patched"):
    sub = [r for r in rows if r["cond"] == cond]
    ph  = sum(1 for r in sub if r["class"] == "placeholder")
    lit = sum(1 for r in sub if r["class"] == "literal")
    mr  = sum(r["reasoning_len"] for r in sub) // max(1, len(sub))
    summary[cond] = (ph, len(sub), lit)
    print(f"{cond:<10}{len(sub):<4}{ph:<13}{lit:<9}{len(sub)-ph-lit:<7}{mr}")

ph_b, n_b, _ = summary["baseline"]
ph_p, n_p, _ = summary["patched"]
print(f"\nFisher baseline vs patched: {ph_b}/{n_b} vs {ph_p}/{n_p}  p = {fisher(ph_b,n_b,ph_p,n_p):.4f}")

# marker frequency: placeholder vs literal traces (baseline only)
base = [r for r in rows if r["cond"] == "baseline"]
tab = defaultdict(lambda: Counter())
for r in base:
    key = "placeholder" if r["class"] == "placeholder" else "literal" if r["class"] == "literal" else "other"
    for h in hits(r["reasoning"]):
        tab[h][key] += 1
print(f"\n{'marker':<20}{'in placeholder':<16}{'in literal':<12}")
for h in MARKERS:
    print(f"{h:<20}{tab[h]['placeholder']:<16}{tab[h]['literal']:<12}")

# quotes: sentences from baseline placeholder traces
print("\n--- quotes (baseline, placeholder class) ---")
shown = 0
for r in base:
    if r["class"] != "placeholder" or shown >= 5:
        continue
    sents = re.split(r"(?<=[.!?])\s+|\n", r["reasoning"] or "")
    pick = [s for s in sents if re.search(r"\{\{|\$|content|read", s, re.I)][:2]
    print(f"\n[{r['item']}] content={r['content']!r}")
    for s in pick:
        print(f"   > {s.strip()[:220]}")
    shown += 1

# write markdown snippet for the paper
md = ["| condition | n | placeholder | literal | other |", "|---|---|---|---|---|"]
for cond in ("baseline", "patched"):
    ph, n, lit = summary[cond]
    md.append(f"| {cond} | {n} | {ph} | {lit} | {n-ph-lit} |")
Path("docs/research").mkdir(parents=True, exist_ok=True)
Path("docs/research/TRACE_RESULTS.md").write_text(
    "# Trace results (auto-generated)\n\n" + "\n".join(md) +
    f"\n\nFisher (baseline vs patched): p = {fisher(ph_b,n_b,ph_p,n_p):.4f}\n")
print("\nwrote docs/research/TRACE_RESULTS.md")
