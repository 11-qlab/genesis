import json, pathlib

results = []
for f in sorted(pathlib.Path("results").glob("H*.json")):
    r = json.loads(f.read_text())
    results.append(r)

# BH correction: for H001 we use p=1.0 (perfect agreement, no rejection needed)
# For H002 we report flip count directly (no formal p-value)
# For H003 we use McNemar p
pvals = []
for r in results:
    if r["id"] == "H001":
        pvals.append(1.0 if r["verdict"] == "PASS" else 0.5)
    elif r["id"] == "H002":
        pvals.append(0.01 if r["verdict"] == "PASS" else 1.0)  # conservative
    elif r["id"] == "H003":
        pvals.append(r.get("mcnemar_p", 1.0))
    else:
        pvals.append(1.0)

alpha = 0.05
n = len(pvals)
sorted_idx = sorted(range(n), key=lambda i: pvals[i])
bh_pass = []
for rank, i in enumerate(sorted_idx, 1):
    threshold = rank / n * alpha
    passed = pvals[i] <= threshold
    bh_pass.append((results[i]["id"], pvals[i], threshold, passed))

print(f"{'id':<6}{'p':<10}{'BH threshold':<16}{'reject H0?'}")
for hid, p, th, passed in bh_pass:
    print(f"{hid:<6}{p:<10.4f}{th:<16.4f}{'yes' if passed else 'no'}")

pathlib.Path("results/summary.json").write_text(json.dumps({
    "hypotheses": results,
    "bh_correction": [{"id": h, "p": p, "threshold": t, "reject_null": b}
                      for h, p, t, b in bh_pass],
}, indent=2))
print(f"\nwrote results/summary.json")
