# Session Handoff — AGI Platform

[Handoff document. Save as docs/research/SESSION_HANDOFF.md, then paste it as the first message of any new session.

```markdown
# Session Handoff — AGI Platform

Read this before touching anything. It is the state of the project
after ~20 hours of work across multiple sessions, most recently a
night spent chasing an AGI-signal measurement on the 20b tier.

The short version: **no AGI signal was found.** One real policy
behavior was confirmed five ways. One suggestive hull measurement
needs one more iteration of bench design. Everything else is
infrastructure that now works and shouldn't be re-litigated.

---

## 1. What this project is

`/root/projects/genesis/AGI` — a modular agentic AI platform. Plan
calculus (planner → typecheck → repair → critique → trace), tool
registry with sandbox, provider router, eval harness with
contamination detection. **Not an AGI.** Infrastructure for
experiments.

The question this session tried to answer: **does the system have a
general mechanism, or a set of lookup tables?** Operational version:
does the model fail *randomly* on tasks within its capability band,
or *clustered by task family*?

That question is still not answered. But the framework for answering
it is now on disk and tested.

---

## 2. Repo state (origin/main)

Look at `git log --oneline -30`. The commits that matter:

| commit message prefix | what it landed |
|---|---|
| `config: raise provider timeout` | `AGI_PROVIDER_TIMEOUT_S` respected; default 600s |
| `providers: fix max_tokens corruption` | `MAX_TOKENS_DEFAULT=4000`; corruption fix; peg-error workaround |
| `families: ...` | 12+3 benches, family tools, MI driver, pre-seed support |
| `artifacts: 12-family distribution MI at 20b` | the 0.195/0.03 MI number |
| `artifacts: hull v3` | the +0.750 gap |
| `T11: ...` | findings doc append |

`docs/research/T11_BROAD_TRANSFER.md` is the long-form record.
Read its tail sections first — they document the most recent
measurements.

---

## 3. Verified findings (with confidence)

Every claim below is backed by an artifact in `artifacts/` or a
commit. Nothing is speculative.

### 3a. Shortest-plan policy — HIGH CONFIDENCE, 5 confirmations

**The 20b model (`gpt-oss-20b`) skips tool calls whose output it
can infer.** When a goal can be solved by writing directly to a
file (because the answer is computable from prior state or general
knowledge), the model produces `[fs_write]` instead of
`[<tool>, fs_write]`.

Confirmed by five independent benches:

| bench | what it should do | what it actually does |
|---|---|---|
| fam06 (conditional) | write→read→conditional-write | write→write (skips read) |
| fam13 (path ambiguity) | two valid paths, either OK | 12/12 shortest path (fs_write→fs_read) |
| fam14in v1 | write→read→write | write→write (skips read) |
| fam15in (Control A) | fs_list→fs_write | fs_write only (guesses "1") |
| fam15out (Control A) | hash_check→fs_write | fs_write only (guesses "mismatch") |

**Consequence for benchmark validity:** any benchmark that can be
shortcut will score near zero regardless of model capability. The
model isn't failing at the task — it's solving it more efficiently
than the plan specifies.

**Fix:** force the tool call by making its output unknowable. Pre-
seeded content the model has never seen does this. Verified with
fam14in v3 (12/12 pass).

### 3b. Pre-seed infrastructure — CONFIRMED WORKING

`bench/families/test/*.jsonl` items can include:

```json
"seed_files": {"seed.txt": "content the model can't infer"}
```

The CLI's before_each hook (src/agi/cli/main.py:544) writes
these files under AGI_FS_ROOT before each item runs. The
implementation was already there. No new code was needed;
earlier confusion was about benchmark.py helpers that turned
out to be dead code.

Smoke test: fam14in-01 seeds seed.txt=seed-01-content, model
produces seq=['fs_read', 'fs_write'], seed.txt and
answer.txt both present in workspace.

3c. Hull measurement v3 — MEDIUM CONFIDENCE

With pre-seeded content and matched 2-step plan shape:

· inside-hull (fs_read on unknown seed.txt): 12/12 = 1.000
· outside-hull (text_regex on unknown seed.txt): 3/12 = 0.250
· gap: +0.750, verdict strongly hull-bounded

Caveat — asymmetric design. Inside was forced (content
unknowable). Outside was not: every pattern in fam14out matches
exactly one line, so counts are guessable. The model didn't
guess most of the time (9/12 failures) — but the asymmetry means
the gap overweights "forced-vs-not" against "familiar-vs-
unfamiliar tool."

Not a clean hull measurement. Suggestive, not conclusive.

3d. Distribution MI — MIXED

Full 12-family run: I(family; pass) = 0.195 bits.

But 5 of 12 families scored 0/12 across all items. Zero
within-family entropy for those, inflating MI. Restricting to the
4 "alive" families (fam05, 07, 08, 09): I ≈ 0.03 bits, both
runs. Variance test showed fam05 moved 2 items between runs,
shifting MI by 0.026. At n=48 per run, signal (0.03) and noise
(±0.05) are indistinguishable.

Interpretation: the 0.195 was measuring bench design (three
difficulty tiers), not capability clustering. The 0.03 is the
honest within-band number, but undersampled.

3e. T11 correction — HIGH CONFIDENCE

The T11 doc's headline "20-tool hurts error_recovery by −0.40" is
a scorer artifact. fs_exists lets the model pre-check before
failing; the expect_subsequence=[fs_read, fs_write, fs_read]
scorer punishes that. The stored 5-tool baseline (17/20 = 0.85)
also doesn't reproduce: three same-day greedy runs on 120b gave
13, 14, 15 out of 20 (mean 0.70).

Documented in T11_BROAD_TRANSFER.md. Any future 120b comparison
must include a same-day greedy control.

---

4. What does NOT work / known issues

No 120b access right now. Groq quota exhausted. Free tier
resets at 00:00 UTC (05:30 IST). NVIDIA retired gpt-oss-120b;
only gpt-oss-20b remains. Cerebras region-blocked. Only working
provider is Colab + llama.cpp + tunnel + gpt-oss-20b.

Colab sessions are ephemeral. /content/ and /tmp/ cleared
on any restart. Only /content/drive/ persists. Everything in
/content/models/ and /content/llama.cpp/ must be restored
from Drive zips each session (~4 min).

Tunnels rotate. cloudflared tunnel --url http://localhost:8081
produces a new *.trycloudflare.com URL on every restart. Update
AGI_BASE_URL each time.

Reasoning-model peg error. gpt-oss-20b on longer goals burns
500-1500 tokens on reasoning before emitting plan JSON. At 800
max_tokens, llama-server returns 500 "output does not match
peg-native format". Current fix is MAX_TOKENS_DEFAULT=4000. This
is a workaround, not a solution.

Jinja vs $step.field substitution. The model writes
{{read_seed_output}} to answer.txt because it uses Jinja
syntax; the platform uses $read_seed.out. Results in literal
placeholders in output files. Does not affect subsequence scoring
(which is what fam14 measures). Same class as tc-09 in
FROZEN.md. Not fixed this session.

time position in zsh. time VAR=val cmd fails in zsh. Use
time cmd with env from export earlier, or VAR=val time cmd
doesn't work either. Put time first then the command.

sed misuse scars. Earlier this session a sed stripped =
from max_tokens=max_tokens, producing max_tokensmax_tokens.
Fixed. Any time a file crashes with NameError or
SyntaxError: invalid syntax where the code looks fine, grep for
missing =. Corruption mode is real.

---

5. Files you'll touch

```
src/agi/tools/family_tools.py       6 new tools (csv_parse, json_extract,
                                    text_diff, text_regex, sqlite_query,
                                    hash_check)
src/agi/tools/__init__.py           registers family_tools when
                                    AGI_TOOLS_FAMILIES=1
src/agi/providers/openai_compat.py  MAX_TOKENS_DEFAULT = 4000
src/agi/evaluation/benchmark.py     pre-seed helpers (dead code — CLI does
                                    the actual seeding at main.py:544)
src/agi/cli/main.py                 whitelist includes family tools when
                                    env set; before_each seeds files
bench/families/seed/*.jsonl         5 examples per family (few-shot seeds)
bench/families/test/*.jsonl         12 items per family (test benches)
scripts/build_families.py           generates 12 families
scripts/build_fam13_14.py           generates fam13/14
scripts/run_nshot_curve.py          N-shot learning curve
scripts/run_distribution_test.py    MI computation, 12 families
scripts/run_path_ambiguity.py       fam13 analyzer
scripts/run_hull_boundary.py        fam14 analyzer
scripts/run_agi_signal.py           3-mode driver (transfer/composition/
                                    contamination)
artifacts/                          eval outputs (gitignored by default;
                                    git add -f to commit)
```

---

6. Commands that work today

Assumes Colab tunnel is live and AGI_BASE_URL points at it.

```bash
# Env
export AGI_PROVIDER_KIND=openai_compat AGI_PROVIDER=colab
export AGI_BASE_URL="<trycloudflare-url>/v1"
export AGI_MODEL=gpt-oss-20b
export AGI_API_KEY_ENV=AGI_API_KEY AGI_API_KEY=local
export AGI_PROVIDER_TIMEOUT_S=300
export AGI_TOOLS_FAMILIES=1

# Sanity
time bin/agi chat "say hi"    # must return in 1-5s

# Single-item eval (fast check)
head -1 bench/families/test/fam14in.jsonl > /tmp/one.jsonl
AGI_STORAGE_PATH=/tmp/o.sqlite3 AGI_FS_ROOT=/tmp/o_ws \
  timeout 300 python3 -m agi eval run \
  --bench /tmp/one.jsonl --seed all --strategy greedy --delay-ms 500

# Hull test (~35 min at 4000 tokens)
python3 scripts/run_hull_boundary.py --out artifacts/hull_new.json

# Path ambiguity test (~10 min)
python3 scripts/run_path_ambiguity.py --out artifacts/path_new.json

# MI test (12 families, ~90 min)
python3 scripts/run_distribution_test.py --runs 1 --out artifacts/mi_new.json
```

---

7. What's next — ranked

7a. Clean hull measurement — highest value, ~1 hour

v3 was asymmetric. Design a matched pair where both benches
force the tool call:

fam16in: seed 3 files with random names, ask "which filename
sorts first alphabetically" — answer requires fs_list.

fam16out: seed content with unpredictable match count, ask
"how many matches for pattern X" — answer requires text_regex.

Both: answer unknowable without the tool. Both: 2-step plan
(<tool>, fs_write). Gap = clean hull effect.

Expected outcomes:

fam16in fam16out reading
12/12 3/12 hull confirmed — tool name is the wall
12/12 8-10/12 text_regex-specific — regex as a language is the wall
12/12 12/12 not hull-bounded — v3 gap was an artifact

Any of the three is a real result. The first is the AGI-signal-
adjacent one.

7b. 120b comparison — 10 min on Groq after 05:30 IST

Run fam16in + fam16out at 120b tier. If gap shrinks (12/12 vs
10/12), hull is tier-dependent. If gap holds (12/12 vs 3/12),
hull is tier-invariant — the stronger finding, because it says
the boundary doesn't move with capability.

7c. Sample-size fix — 3 hours

The 0.03 alive-band MI is not distinguishable from noise. Either
more runs (fam05, 07, 08, 09, --runs 5) or more items per
family. Won't fit one session.

7d. The 50-cold-family distribution test — 2 weeks

The protocol that would actually produce an AGI signal: 50 new
task families, frozen and hashed, run once, publish full table.
Not doable in a session. Documented in earlier messages.

7e. Fix the {{var}} substitution bug — 2 hours

Add {{name}} handling in the plan executor so {{read_seed_output}}
resolves to $read_seed.out. Closes a class of answer-correctness
failures. Doesn't affect tool-planning measurements but improves
everything else.

---

8. What not to do

· Don't design benches where the answer is inferable from prior
  state. The model will shortcut the tool call and score zero
  regardless of capability. This burned 4 separate bench designs
  this session.
· Don't trust Groq baselines without same-day greedy control.
  The stored 0.85 didn't reproduce; three samples gave 0.70.
· Don't use time VAR=val cmd in zsh. Reserved word parse
  error.
· Don't assume Colab stays up. Restore from Drive every
  session. Keep-alive cell running throughout any >20 min task.
· Don't re-run fam14 v1 or v2. They measure shortcut policy
  or planner rejection of conditionals, not hull effect.
· Don't interpret I(family; pass) = 0.195 as a signal. It's
  bench-design clustering. The alive-band 0.03 is the honest
  number, and it's undersampled.
· Don't invent tools on the fly. text_regex, hash_check,
  sqlite_query are in family_tools.py but only register with
  AGI_TOOLS_FAMILIES=1. Without that env var, plan validation
  rejects them.

---

9. Honest framing

Twenty hours produced:

· One real policy finding, confirmed 5 ways.
· One suggestive hull measurement needing one more bench design.
· A working pre-seed pipeline.
· An inconclusive N-shot curve.
· A corrected T11 (scorer artifact + baseline drift).
· Infrastructure that no longer crashes.

No AGI signal. That's the answer to the question that started
the session. The question remains open because nobody has a clean
measurement framework for it. This project now has a candidate
framework (matched-complexity tool planning with forced content),
and one data point suggesting a boundary exists at 20b tier.

The next session's first task is 7a — the clean hull pair. If that
comes back clean, the project has its first defensible AGI-adjacent
result. If it comes back flat, the v3 gap was an artifact of
asymmetric design and the whole hypothesis needs rework.

Both outcomes are publishable. Both are honest. Neither is AGI.

---

10. First actions for a fresh session

1. cd /root/projects/genesis/AGI && git log --oneline -10 — confirm
   you're at the tip.
2. git pull origin main — sync.
3. Read the last 100 lines of docs/research/T11_BROAD_TRANSFER.md.
4. Check artifacts/ — the last measurement files.
5. Ask the user: "continue the hull measurement (7a), or pick a
   different thread?"
6. Set up provider env. Test with bin/agi chat "say hi".
7. Only then touch code.

If the user says "where were we," point them at section 7a. If they
say "is there signal," point them at section 9. If they say "just
run something," run the fam14 hull again to re-verify the +0.750
(20 min) while designing fam16.

```

That's the handoff. It's ~350 lines, standalone, every claim tied to a commit or artifact, and it leads with the honest answer rather than burying it. A new AI can read this in 5 minutes and know exactly what's real.

Two things not in the doc but worth knowing: the user has been extremely patient through a long session with many failures. The doc respects that by not inflating anything. And the doc is designed so a fresh session doesn't re-litigate infrastructure — it points at what's working and what the next decision is.]

---

## Session 2 addendum — 2026-10-24

### Fourth T11 correction: the +0.750 hull gap is NOT reproducible

`hull_20b_v3.json` (inside 12/12, outside 3/12, gap +0.750) does not
reproduce on the same model. Testing `fam14in-01` returned
`status=error, duration=81.7s, "no JSON object found"` — the *same*
error as `fam15in-01`. The +0.750 was measured on a run where CoT fit
the token budget for inside items but not outside items. It is a
CoT-length stratification, not a capability boundary.

### Root cause — CoT truncation in the provider

`src/agi/providers/openai_compat.py` sent `max_tokens=4000` with a 60s
timeout. `gpt-oss-20b` reasoning filled the budget on longer goals,
returned `content=""` + truncated `reasoning_content`, and
`planner.py:88` could not find `{...}`.

Fixed (commit 9c20e1a): `MAX_TOKENS_DEFAULT` 4000→6144, timeout
60→240s, retry-on-truncation with a hard JSON-only nudge.

Verification: `fam14in-01` under the fix is 35.4s, `succeeded`,
`tools=['fs_read','fs_write']` — first clean pass on the same item
that failed pre-fix.

### Second bug, newly surfaced — plan schema validation

`fam14out-01` under the fix now returns
`plan schema validation failed: goal Field required, input_value={}`.
The model emits JSON (fix works) but it is `{}`. Previously masked
by truncation.

### The hull question

Unknown. v3 cannot be used as a baseline. Correct next steps:
1. Fix plan schema (`goal` optional → default `item.goal`, or log raw
   completion text so `{}` is inspectable).
2. Re-run 4-item smoke on fam14in/fam14out under both fixes.
3. Only then point `cfh probe` at fresh trajectories.

### What was built

`cfh/` — counterfactual hull probe. Generates near-miss twins (swap
arg, swap tool, stale observation, hallucinate field, reorder, and
the shortcut twin: replace a tool call with the model's own inferred
result). Asks the same model to discriminate under position control.
Reports accuracy + bootstrap CI + hull gap. Tested end-to-end against
a live gpt-oss-20b tunnel.
