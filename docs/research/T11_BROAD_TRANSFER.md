# T11 — Broad transfer (§1 from AGI_REQUIREMENTS.md)

**Question:** Does the planner maintain accuracy when the tool catalog
is expanded 4×? The default catalog is 5 tools (`fs_list`, `fs_read`,
`fs_write`, `memory_search`, `shell`). Extended is 20 (`+fs_exists`,
`fs_size`, `fs_mkdir`, `fs_move`, `fs_delete`, `fs_glob`, `text_*`,
`hash_*`, `base64_*`, `json_get`).

**Method:** Same 3 benchmarks, same model (`gpt-oss-120b`), same 9-key
pool. `AGI_TOOLS_EXTENDED=1` toggles the extended catalog. Single-run
screen; not multi-run.

## Data (2026-10-20)

| benchmark | 5-tool | 20-tool | delta | rate_limited |
| --- | --- | --- | --- | --- |
| workspace_list_hard | 1.00 (20/20) | 0.90 (18/20) | **-0.10** | 1 |
| task_chain | 0.95 (19/20) | 0.90 (18/20) | **-0.05** | 0 |
| error_recovery | 0.85 (17/20) | **0.45** (9/20) | **-0.40** | 0 |

## Interpretation

### workspace_list_hard — probably noise

Delta -0.10 is at the noise-band boundary; 1 of 20 items hit rate
limit at 6000ms pacing (20-tool prompts are ~40% heavier per call so
6000ms is tighter for 20-tool than for 5-tool). The -0.10 may be -0.05
or 0 on a clean run. Not distinguishable from noise.

### task_chain — inside noise

Delta -0.05 is well inside the 0.15 noise band. Catalog expansion does
not measurably affect this benchmark.

### error_recovery — real, mechanism partially identified

Delta -0.40 is well outside noise. 0 rate-limited items, so this is a
genuine effect.

**Mechanism (single-item confirmation):** with 20 tools, the model
chooses `fs_exists` as a first step (pre-check), then `fs_read` fails
(missing file, as the benchmark expects), then `Coordinator`'s recovery
loop fires, creates the file, and retries `fs_read` successfully. The
observed tool sequence on `er-01` was `[fs_exists, fs_read, fs_write,
fs_read]` — which **contains** `[fs_read, fs_write, fs_read]` as a
subsequence, so `er-01` passes at 20 tools.

**But the aggregate is 9/20, not 20/20.** So 11 of 20 items fail. Not
yet itemized which or why. Candidates (not confirmed):

1. `fs_exists` on some items may return "yes" (file already created by
   a prior item's recovery or prior condition's run). The pre-check
   then succeeds, `fs_read` succeeds on the first try, `fs_write` never
   fires, and the required `[fs_read, fs_write, fs_read]` subsequence
   fails.
2. `fs_exists` on some items may return "no" and the model may decide
   "file doesn't exist, can't complete the task" rather than attempting
   the recovery path.
3. Cross-item workspace contamination from prior benchmarks or prior
   conditions in the same `AGI_FS_ROOT` may create some files before
   their item runs.

Follow-up needed to distinguish. Recorded as open, not chased in this
batch.

## What this batch established

- 4× catalog expansion is **measurably harmful** on
  `error_recovery.jsonl` at n=20, single run (-0.40, 0 rate-limited).
- Effect on `workspace_list_hard` (-0.10 with 1 rate-limited item) and
  `task_chain` (-0.05) is within or at the boundary of noise.
- The mechanism is **partial**: on the one item we traced end-to-end,
  the extended catalog produces a recovery trace that still satisfies
  the benchmark's subsequence requirement. On 11 other items something
  else happens that we haven't identified.

## What this batch did not establish

- Whether the -0.40 survives multiple runs (single-run only here).
- Whether workspace contamination is the cause of the 11 failing items.
- Whether `workspace_list_hard` -0.10 is real or noise.
- Any claim about generalization to other benchmarks, models, or
  catalog sizes.

## A separate bug found during this batch

`SimpleAgent` (used by `agi run`) recorded step-failed events but
continued to the next step and reported the run as `succeeded` even
when a step's `ok=False`. Only `ToolError` (validation) aborted the
loop. This is pre-existing and unrelated to §1; see the regression test
`tests/unit/test_simple_agent_stops_on_failure.py`. **Eval measurements
are unaffected** because `agi eval run` uses `Coordinator`, which does
break on failed steps.

## Prior expectations, corrected

I expected a 4× catalog to hurt uniformly (worse tool selection across
the board). It didn't. `task_chain` was unaffected; `error_recovery`
collapsed. The difference is that `error_recovery` items are
specifically designed to force a particular failure-then-recovery
sequence, and `fs_exists` lets the model pre-check rather than fail
blind. This is the same class of brittleness as T9's novel-ordering
check: the benchmark rewards a specific shape of wrongness, not the
goal.

## Follow-up — mechanism identified (2026-10-20)

20-tool error_recovery re-run with per-item `tool_sequence` exposed.

    summary: accuracy=0.55, passed=11/20, rl=1

### Failing items never call fs_write

9 of 9 annotated failures show the same signature:

    ['fs_exists', 'fs_read', 'fs_exists', 'fs_list', 'fs_glob']

The model pre-checks with fs_exists, reads (fails, missing file), then
escapes into cheap inspection tools (fs_list, fs_glob) instead of the
creating tool. Coordinator recovery only fires when a step's ok=False;
fs_list/fs_glob return empty Ok=True, so no failure surfaces to
trigger recovery.

### Passing items reach fs_write via longer detour

    ['fs_exists', 'fs_read', 'fs_exists', 'fs_list', 'fs_write', 'fs_read']

Subsequence intact, item passes, but at higher token cost.

### Mechanism in one sentence

Extended catalog gives the model escape routes after failure that the
benchmark doesn't expect, and it prefers the cheap ones over fs_write.

### Two extra greedy + two extra T13-basic runs invalidated

Four new runs (greedy 0.60, 0.55; T13-basic 0.20, 0.15) were 20-tool,
not 5-tool: AGI_TOOLS_EXTENDED=1 leaked from an earlier diagnostic.
Discarded from T13 multi-run dataset.

T13-basic multi-run: 4 samples (0.80, 0.85, 0.90, 0.95, mean 0.875)
vs greedy 3 (0.75, 0.80, 0.80, mean 0.7833). Delta +0.09, below noise
band. No conclusion beyond that.


## T13 on a 3B model — phone deployment (2026-10-21)

Dolphin 3.0 Llama 3.2 3B Q4_K_M, llama.cpp on 4 CPU threads.

**Greedy: 0/5. Revision-basic: 0/5. No rescue at this tier.**

Three failure modes on 3B:

1. **Escape without recovery.** Items 1, 3, 4, 5: `[fs_read, fs_list, fs_read]` — reads, fails on "not a file", lists, retries the same read. Never calls `fs_write`.

2. **Path hallucination.** Items 4, 5: prepends `sandbox_root/` to every path, which doubles inside the sandbox and returns `not found`.

3. **Revision schema violation.** All three revision attempts rejected by pydantic: `steps.N.title Field required`. The initial planner prompt elicits `title`; the revision prompt does not. Same model, two elicitations, two compliance rates.

Item 2 (er-02) produced `[fs_read, fs_list, fs_list, fs_read, fs_write, fs_read]`, which contains the required subsequence. The run still scored failed because the final status was `failed` — the model wrote to `result.txt` (literal goal) instead of recovering `secret.txt`. The scorer requires `status: succeeded` AND the subsequence, and only the first failed.

**Conclusion:** T13 is capability-gated. At 3B tier, revision cannot rescue the recovery failure because the model cannot produce schema-valid revision plans. Revision helps only when the base model is already capable of the task — it accelerates improvement, it does not create capability.

**Infrastructure finding:** default provider timeout is 60s x 3 attempts = 180s. Any on-device model below ~10 tok/s times out 100% of planner calls. Raise via `AGI_PROVIDER_TIMEOUT_S=600`. Verified: 0 timeouts at 600s across 10 planner calls (greedy + revision, 5 items each).

### Revision prompt postmortem (b3)

After fixing `title` and `args` enumeration in t13_revision.py:

- `title` schema rejections: 3 -> 1 (variance, not regression)
- `args` empty `{}` failures: still present on er-01, er-03
- Pass rate: 0/5 unchanged

Infrastructure verified correct: `registry.describe()` exposes `args_schema` (line 33), every tool class declares `args_model` (fs.py:29, 59, 108), `Planner` renders `- path: str *required*` into the prompt (planner.py:49-61).

`bin/agi plan "read config.txt..."` produces correct args on a single call. Eval runs produce `args: {}` intermittently on 5-item batches. Conclusion: the 3B is below the reliability threshold for consistent arg production under eval load. Two prompt bugs fixed; capability remains the wall.

### 120b revision cross-check (2026-10-22)

Two 5-item `error_recovery` runs on `openai/gpt-oss-120b` via Groq with
`--strategy revision --revision-signal basic`, after the `title` and `args`
prompt fixes in `t13_revision.py`:

- hf_test: 3/5 = 0.60
- t13_check: 4/5 = 0.80

Combined 7/10 = 0.70, 95% CI roughly [0.40, 0.90]. The T11 5-tool greedy
baseline is 0.85 (17/20). **Within the confidence interval — cannot claim
revision improves or degrades at 120b from two 5-item samples.**

Revision fires on 120b (confirmed: `revision plan invalid` line in t13_check
log). One failure mode: model picks tool `shell` on a revision attempt.
`shell` is in `TOOL_SIGNATURES` but disabled by `AGI_SHELL_ENABLED=false` in
the current config. 120b knows the tool name from training priors and reaches
for it despite the catalog not including it. This is a distinct failure mode
from the 3B's escape-into-inspection behavior — 120b's revision actively
introduces a wrong tool rather than escaping to a cheap inspection tool.

**Prompt fixes verified necessary at 120b** (4/5 items passed; if title/args
were missing on revisions, those would fail schema).

**Next measurement required:** 20-item revision run at 120b to distinguish
from greedy baseline. Blocked on Groq daily quota reset (05:30 IST).

### T13 20-item 120b — direct same-day comparison (2026-10-22)

Both arms, same model, same bench, same quota window, ~3 min apart:

- greedy: 14/20 = 0.70
- revision-basic: 16/20 = 0.80
- delta: **+0.10 in favor of revision**

95% CI: greedy [0.52, 0.88], revision [0.64, 0.96]. Intervals
overlap; the point estimate favors revision but n=20 single-run
per arm is not enough for a confident claim.

**Consistent with the T11 doc's +0.09 claim** (from 5-vs-6 sample
multi-run). The direct same-day comparison supports the direction
of the T13 effect, not just the direction stated in the doc.

### Finding: T11 greedy baseline does not reproduce

T11 doc baseline: 5-tool greedy on error_recovery = 17/20 = 0.85.
Same bench, same model (openai/gpt-oss-120b via Groq), same day as
the revision run: 14/20 = 0.70. Delta from stored baseline: -0.15,
outside the 0.15 noise band.

Either the model drifted since the baseline was measured, the
stored baseline was a high sample, or conditions (quota, system
load) affect performance materially. Any of these invalidates
0.85 as a canonical reference. The 17/20 number should not be
quoted without a same-day greedy control alongside.

### Revision-specific failure modes (16/20 arm, 4 failures)

- er-01: revision used `fs_glob` (extra.py only, AGI_TOOLS_EXTENDED off)
- er-07: revision used `shell` twice (AGI_SHELL_ENABLED=false)
- er-02, er-04: initial `fs_read` failed, no recovery fired

Two of the four failures are revision-specific: 120b reaches for
tools outside the active catalog during revision. Typechecker
rejects, item falls back to original plan. Cost: extra calls,
no benefit. Even so, revision's net delta vs same-day greedy is
positive (+2 items rescued).

### Contamination probe + greedy baseline drift (2026-10-22)

Contamination: error_recovery before/after a workspace_list prep run.

- B fresh: 15/20 = 0.75
- B after A: 13/20 = 0.65
- delta: -0.10
- verdict: clean (within noise)

No evidence of cross-bench state leakage. Prior eval results valid.

### T11 greedy baseline does not reproduce today

Three clean greedy samples on error_recovery, 20 items each,
same day, same model (openai/gpt-oss-120b via Groq):

- 13/20 (transfer mode's er run)
- 14/20 (greedy_20 direct run)
- 15/20 (contamination B fresh)

Mean 14/20 = 0.70. T11 stored baseline: 17/20 = 0.85.
Delta: -0.15, outside the 0.15 noise band. Std across samples
~1.0, 95% CI on the mean roughly [0.59, 0.78].

The stored 0.85 is outside that interval. **The T11 baseline
0.85 is inflated.** Either the historical measurement was
high-sample, or conditions (model version, provider quota,
system load) affect performance by ~0.15.

Consequence for T13: revision 16/20 = 0.80 vs today's greedy
mean 0.70 → delta +0.10. Direction of the T13 claim holds.
Absolute values in the doc (greedy 0.85, revision 0.94) are
both inflated by the same factor, so the +0.09 delta claim is
directionally consistent but absolute numbers should not be
quoted without a same-day control.

### T13 tier comparison (2026-10-23)

Three tiers, error_recovery, composition mode.

| tier | provider | greedy | rev-basic | rev-rich |
|---|---|---|---|---|
| 3b | phone llama.cpp | 0/5 | 0/5 | not run |
| 20b | Colab T4 gpt-oss-20b | 3/5=0.60 | 3/5=0.60 | 3/5=0.60 |
| 120b | Groq gpt-oss-120b | 14/20=0.70 | 16/20=0.80 | not run |

**20b delta: 0.000.** No effect from revision at 20b tier.
120b delta: +0.10.

**Interpretation.** Two readings:

1. T13 mechanism requires ≥120b tier. Greedy scales gently
   (0.00 -> 0.60 -> 0.70), but revision only adds value at 120b.
   Below that, the critique pass produces plans that typecheck
   but don't improve recovery outcomes.

2. n=5 at 20b is too weak to distinguish +0.00 from +0.10.
   Only 120b (n=20) has enough items to resolve the delta.

Both readings support the same conclusion: the 20b tier adds
no evidence for T13 and does not contradict it. Any writeup
should present it as the honest middle, not as a confirmation
or refutation.

**Infrastructure note.** 20b on T4 (llama.cpp, 52 tok/s):
planner prompts run ~600 tokens typical, ~6870 worst case.
The 6870-token runaway calls occur roughly once per ~5 items
and cost ~130s each. At n=20 per arm, one or two runaways per
arm can push a 20-item bench past a 900s client timeout.
Recommended floor for 20b tier: 1800s per arm.

### Distribution test: MI within alive band (2026-10-24)

The 12-family distribution test measured I(family; pass) = 0.195 bits
on gpt-oss-20b. That number is inflated by 5 families that scored 0.00
across all 12 items (fam01, fam03, fam04, fam06, fam11). Within-family
entropy for those is 0, dragging H(pass|family) down.

Constraining to the 4 "alive" families (fam05=0.33, fam07=0.33,
fam08=0.25, fam09=0.58 in run A): I = 0.047 bits. Run B same four:
I = 0.021 bits. Combined ~0.03.

**Interpretation.** The 0.195 was measuring "bench has three tiers of
difficulty." The 0.03 is measuring "within the alive band, failures
don't cluster by family." The latter is the AGI-adjacent signal:
failing randomly within a difficulty band is what a general mechanism
would do; failing clustered by family would be a narrow agent.

But: n=48 per run means the estimator noise exceeds the signal. fam05
moving 2 items shifted MI by 0.026. Cannot distinguish 0.03 from 0.10
without more samples per family.

**Next measurement.** Same 4 families at 120b tier. If MI stays <0.1,
scattered-within-alive is a stable property independent of capability.
If MI rises to ~0.2, capability introduces structure where none existed.
