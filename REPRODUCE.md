# Reproduction

## Prereqs

- Python 3.10+
- `pip install openai`
- Environment:
  - `OPENAI_BASE_URL` (e.g. `https://api.groq.com/openai/v1`)
  - `OPENAI_API_KEY` (your provider key — do NOT commit)
  - `MODEL` — one of: `openai/gpt-oss-120b`, `qwen/qwen3.8-27b`, `allam-2-7b`

## Setup (once per session)

### 1. Seed the SQLite database

    python3 seed_db.py

### 2. Start the HTTP server (family D requires it)

    pkill -f stub_server.py 2>/dev/null; sleep 0.5
    python3 stub_server.py &
    sleep 1
    curl -sf http://localhost:8088/status.json && echo " <- server ok"

Keep this terminal open. If you close it, the server dies — re-run this block.

### 3. Verify the model is reachable

    python3 - <<'VERIFY'
    import os
    from openai import OpenAI
    c = OpenAI(base_url=os.environ["OPENAI_BASE_URL"], api_key=os.environ["OPENAI_API_KEY"])
    r = c.chat.completions.create(model=os.environ["MODEL"], temperature=0,
                                  messages=[{"role": "user", "content": "ok"}])
    print("model ok:", r.model)
    VERIFY

If this fails with 404, the MODEL id is not on your account — query
`curl -s $OPENAI_BASE_URL/models -H "Authorization: Bearer $OPENAI_API_KEY"`
for the list your key can serve.

## Run one model, all conditions

    ./run_all.sh openai/gpt-oss-120b

The script:
- Refuses to run if `stub_server.py` is not up
- Refuses to run if the model is not reachable
- Writes `results/runs_${SAFE}.jsonl` (60 records)
- Writes `results/report_${SAFE}.md` (aggregate table)
- Writes `results/mcnemar_${SAFE}.txt` (McNemar + BH)

`SAFE` = the model id with `/` replaced by `_` (e.g. `openai_gpt-oss-120b`).

Run three times, once per model:

    ./run_all.sh openai/gpt-oss-120b
    ./run_all.sh qwen/qwen3.8-27b
    ./run_all.sh allam-2-7b

## Committed results — do not overwrite

The following files are the reference evidence for the paper. If you
re-run, work in a scratch directory or use a custom SAFE suffix; do not
overwrite these:

- `results/runs_openai_gpt-oss-120b.jsonl`
- `results/runs_qwen_qwen3.8-27b.jsonl`
- `results/runs_allam-2-7b.jsonl`
- `results/report_*.md`
- `results/mcnemar_*.txt`

## Reading the report

Each row is `n / success / placeholders / errors / rate`:

- `success` — argument value equals the prior observation after `.strip()`
- `placeholders` — argument contained `<...PLACEHOLDER...` AND differed from observation
- `errors` — an exception was raised before the check (dispatch, JSON parse, etc.)

**`errors > 0` is not a model failure.** Run `python3 diagnose_live.py`
before interpreting an `errors > 0` cell. Seven distinct harness bugs
produced `errors > 0` in this session, all documented in `results/NOTES.md`.

## Known anomaly — read before citing prompt_patch

`results/NOTES.md` documents a prompt_patch anomaly on qwen-C and
allam-C (8 and 9 errors respectively, where baseline had 0). Do not
cite prompt_patch rows for those models until diagnosed.

## Harness internals

- `executor_patch` never calls the model. It substitutes `expect_arg`
  from the prior observation mechanically — 100% success by construction.
- `baseline` = natural prompt (`The prior tool observation was: ...`).
- `prompt_patch` = natural + explicit "copy character-for-character"
  instruction added after gpt-oss-120b's single D02 format failure.
- The placeholder counter misses hallucinated substitutions. See
  `results/NOTES.md`, allam-2-7b case.
