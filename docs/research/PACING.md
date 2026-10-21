# Pacing, contamination, and why the 2026-10-20 experiment failed

## The number that matters

Effective tokens-per-minute (TPM) = `(items × per_item_tokens × 60) / wall_seconds`

Where `per_item_tokens` ≈ 2,000 for the current planner prompt
(900 input + 300 output for plan, 500 input + 100 output for summary,
plus retries).

For a 20-item run at `--delay-ms 5000`:
- wall_seconds ≈ 20 × 5 = 100
- tokens ≈ 20 × 2,000 = 40,000
- effective TPM = 40,000 × 60 / 100 = **24,000**

Groq's free-tier limit for `openai/gpt-oss-120b` is **8,000 TPM**.
The run exceeds it by 3×. Every item after the first window is a
potential 429.

## The failure sequence (verbatim from 2026-10-20)

    tpc_u_1: 20/20   # first 100s: budget available
    tpc_u_2: 14/20   # next 100s: 6 items 429'd
    tpc_u_3:  0/20   # next 100s: every item 429'd

The accuracy drop is not model noise. It is tier exhaustion. The
three samples share the same model, endpoint, prompt, and code. The
only variable is the rate-limit window state.

`bench/README.md`'s spread rule (>0.15 → no point estimate) is
exactly the rule that would have caught this. It wasn't applied
before the run. It is applied now — the contamination protocol
automatic-flag any run with >10% rate-limited items.

## How to pace safely

Given a tier limit L (tokens/min) and per-item cost c (tokens):

    safe_delay_seconds = ceil((items × c × 60) / L / items)

Which simplifies to:

    per-item wall seconds ≥ c × 60 / L

For Groq 8k TPM and c ≈ 2,000:
- per-item wall seconds ≥ 2000 × 60 / 8000 = **15 seconds**
- so `--delay-ms 20000` is safe; `--delay-ms 5000` is not

For a 20-item run at 20s pacing:
- wall_seconds = 400
- effective TPM = 40,000 × 60 / 400 = 6,000 ✓

## The prompt-shrink lever

`--delay-ms 20000` works but makes runs painfully slow (3-4 hours
for an 18-run experiment). The alternative is to cut `c` (per-item
cost). The current prompt is ~900 tokens; most of that is the tool
catalog with descriptions and arg schemas.

Option: replace the catalog with tool names + one-line descriptions.
Reduces input tokens to ~400. Effective c → ~1,200. Then:

    per-item wall seconds ≥ 1200 × 60 / 8000 = 9 seconds
    `--delay-ms 10000` becomes safe

Downside: less guidance to the model. Which is testable — run the
same benchmark with the short prompt at 10s pacing, compare accuracy
at the same contamination threshold. If accuracy holds (spread
<0.15 across 3 clean runs), the prompt was padded; if it drops, the
descriptions were load-bearing.

## Rules added to the codebase as a result

1. `bench/README.md` contamination rule: >10% rate-limited items ⇒
   discard the run.
2. `EvalRunner` marks contaminated runs with `status: contaminated`
   and exits 3 (distinct from accuracy failure).
3. `agi eval run` prints a `CONTAMINATED` banner in stderr and a
   markdown banner at the top of the report.
4. No point estimate is recorded from fewer than 3 clean runs.

## The honest state as of 2026-10-20

The typed_chain experiment was invalidated by rate limits. That is a
real result about the experiment, not about the code. The code has
zero responsibility for the 24,000 TPM number — that is the
experiment design (20 items, 5s pacing, 2k tokens per item, 8k tier).
