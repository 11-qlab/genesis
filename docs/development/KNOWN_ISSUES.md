# Known Issues

## Functional
- `OpenAICompatProvider.stream` has no reconnect on mid-stream failure. It
  raises `ProviderError` and the caller decides. Acceptable for CLI use; a
  long-lived server would need backoff and a partial-response cache.
- `SimpleAgent` records `step.failed` and then aborts the whole run on the first
  tool error. There is no per-step retry policy yet. This is deliberate: silent
  retries of side-effecting tools are worse than a clean failure.
- The planner prompt asks for JSON in a fixed shape. `extract_json_object`
  tolerates fenced blocks and leading/trailing text, but a model that emits
  several JSON objects in one reply will only yield the first. Fine for the
  single-plan case; revisit before supporting nested plans.

## Memory / retrieval
- `mem-eval`'s goal ("search the notes about the eval runner storing per
  item rows") is the one item on the edge. It passed against
  `openai/gpt-oss-120b` after the step24 prompt-catalog fix, but the wording
  says "notes" and a smaller model could plausibly choose `fs_list` again.
  If a future model or prompt regresses that item, the correct interpretation
  is "this model chose a defensible alternative for a goal that names the
  domain ('notes') but not the action ('search memory')". Do not change the
  benchmark to make it pass; record the failure and decide whether the
  benchmark should accept either tool as valid for that item.

- `HashEmbedding` is a lexical hash sketch, not a semantic embedder. It gives
  real signal for tests and offline use, but it will not match a query with
  different vocabulary that is semantically equivalent. Switch to
  `openai_compat` embeddings for real semantic retrieval.
- `FlatIndex` is `numpy`-only. It holds the whole embedding matrix in memory
  and scans it linearly per query. Fine at thousands of chunks; not at
  millions. When it becomes a bottleneck, split into a `VectorIndex` protocol
  with a `FlatIndex` default and an optional FAISS or sqlite-vec backend.
- `openai_compat` embeddings do not batch across documents yet; a 500-chunk
  ingest makes one request per chunk. Batching is a Phase 8 optimization,
  not a correctness bug.

## Operational
- `state/agi.sqlite3` is not vacuumed. Run size grows with the event log. For
  long-lived usage add a `runs prune` CLI or a cron job calling
  `sqlite3 state/agi.sqlite3 'VACUUM'`.
- Logging writes to stderr; file logging is not wired. That is intentional at
  this stage — the CLI is expected to be run interactively.

## Testing
- `tests/integration/test_cli.py` shells out to `python -m agi`. It is slower
  than the rest (subprocess startup ~150 ms/test), but it is the only test that
  proves the console entry point works from a clean environment.
- Coverage gate: fail_under=63 (measured 68.73%) [fixed in bf799c0]. `pytest --cov` is available if wanted; the current suite
  focuses on branch-relevant behavior rather than lines.

## Deferred by policy (not bugs)

- **Training execution.** Three independent gates prevent an accidental
  training run:  requires ,  is
  unimplemented, and no adapter ships in the repo. Removing any one gate does
  not enable training. See  D011.
- **Remote API binding.**  refuses to bind any host other than
   /  /  unless  is passed. The
  API can execute tools, so loopback is the safe default.
- **Obtaining file:///root/projects/genesis/AGI
  Installing build dependencies: started
  Installing build dependencies: finished with status 'done'
  Checking if build backend supports build_editable: started
  Checking if build backend supports build_editable: finished with status 'done'
  Getting requirements to build editable: started
  Getting requirements to build editable: finished with status 'done'
  Installing backend dependencies: started
  Installing backend dependencies: finished with status 'done'
  Preparing editable metadata (pyproject.toml): started
  Preparing editable metadata (pyproject.toml): finished with status 'done'
Requirement already satisfied: pydantic<3,>=2.6 in /root/ENVS/quantum/lib/python3.13/site-packages (from agi-platform==0.1.0) (2.13.5)
Requirement already satisfied: rich>=13.7 in /root/ENVS/quantum/lib/python3.13/site-packages (from agi-platform==0.1.0) (15.0.0)
Requirement already satisfied: typer<1,>=0.12 in /root/ENVS/quantum/lib/python3.13/site-packages (from agi-platform==0.1.0) (0.27.3)
Requirement already satisfied: annotated-types>=0.6.0 in /root/ENVS/quantum/lib/python3.13/site-packages (from pydantic<3,>=2.6->agi-platform==0.1.0) (0.8.0)
Requirement already satisfied: pydantic-core==2.46.5 in /root/ENVS/quantum/lib/python3.13/site-packages (from pydantic<3,>=2.6->agi-platform==0.1.0) (2.46.5)
Requirement already satisfied: typing-extensions>=4.14.1 in /root/ENVS/quantum/lib/python3.13/site-packages (from pydantic<3,>=2.6->agi-platform==0.1.0) (4.16.0)
Requirement already satisfied: typing-inspection>=0.4.2 in /root/ENVS/quantum/lib/python3.13/site-packages (from pydantic<3,>=2.6->agi-platform==0.1.0) (0.4.4)
Requirement already satisfied: shellingham>=1.3.0 in /root/ENVS/quantum/lib/python3.13/site-packages (from typer<1,>=0.12->agi-platform==0.1.0) (1.5.4)
Requirement already satisfied: annotated-doc>=0.0.2 in /root/ENVS/quantum/lib/python3.13/site-packages (from typer<1,>=0.12->agi-platform==0.1.0) (0.0.5)
Requirement already satisfied: markdown-it-py>=2.2.0 in /root/ENVS/quantum/lib/python3.13/site-packages (from rich>=13.7->agi-platform==0.1.0) (4.2.0)
Requirement already satisfied: pygments<3.0.0,>=2.13.0 in /root/ENVS/quantum/lib/python3.13/site-packages (from rich>=13.7->agi-platform==0.1.0) (2.21.0)
Requirement already satisfied: mdurl~=0.1 in /root/ENVS/quantum/lib/python3.13/site-packages (from markdown-it-py>=2.2.0->rich>=13.7->agi-platform==0.1.0) (0.1.2)
Building wheels for collected packages: agi-platform
  Building editable for agi-platform (pyproject.toml): started
  Building editable for agi-platform (pyproject.toml): finished with status 'done'
  Created wheel for agi-platform: filename=agi_platform-0.1.0-py3-none-any.whl size=3274 sha256=c96a4fada064e9bec1a3ad56febb0b68184f0921946385d6ab7a75b5be909295
  Stored in directory: /tmp/pip-ephem-wheel-cache-jd33l3s0/wheels/d6/5a/6f/27a5ca43cf809d468d51e441df17d9ba76753e95daa04acd5e
Successfully built agi-platform
Installing collected packages: agi-platform
Successfully installed agi-platform-0.1.0.** The project ships a                                                            
 Usage: python -m agi [OPTIONS] COMMAND [ARGS]...          
                                                           
 AGI research platform CLI.                                
                                                           
╭─ Options ───────────────────────────────────────────────╮
│ --install-completion          Install completion for    │
│                               the current shell.        │
│ --show-completion             Show completion for the   │
│                               current shell, to copy it │
│                               or customize the          │
│                               installation.             │
│ --help                        Show this message and     │
│                               exit.                     │
╰─────────────────────────────────────────────────────────╯
╭─ Commands ──────────────────────────────────────────────╮
│ version  Print the CLI version.                         │
│ doctor   Diagnostics: python, config, provider, tools,  │
│          storage path.                                  │
│ health   Full health snapshot; exit 1 if providers are  │
│          unhealthy.                                     │
│ tools    List registered tools and their argument       │
│          schemas.                                       │
│ chat     One-shot chat with the active provider.        │
│ plan     Ask the planner for a validated plan; do not   │
│          execute it.                                    │
│ run      Plan and execute a goal end-to-end, recording  │
│          all events.                                    │
│ serve    Run the loopback HTTP API.                     │
│ runs     List recent runs.                              │
│ show     Show a run's record and its event log.         │
│ config   Configuration helpers.                         │
│ eval     Evaluation commands.                           │
│ train    Training commands (default: no execution).     │
╰─────────────────────────────────────────────────────────╯ wrapper instead. An
  editable install would pull  over the network on first build,
  and the training restriction also forbids side-effecting network actions
  in this environment. The wrapper behaves identically.
- **Checkpoint file verification.** 
  checks that the file exists, not that its hash matches. Hash verification
  is a Phase 7 follow-up once a real adapter produces artifacts.

## T5 episodic memory — Jaccard retrieval limitation

`EpisodicMemory.retrieve_similar` uses Jaccard similarity over lowercased
word tokens. On short goals, this produces near-ties that are semantically
arbitrary (`list everything` cannot distinguish `list the files` from
`list the workspace`). The mechanism works; the retrieval quality is
bounded by the similarity metric.

**Fix:** replace Jaccard with embeddings. `memory/embeddings.py` already
provides `HashEmbedding` (still lexical, would not fix this) and
`OpenAICompatEmbedding` (needs a real embedding provider). A follow-up
batch can swap the metric in `_jaccard` for a call to an embedder.

**Data:** see `docs/research/T5_RETRIEVAL_RESULTS.md` for the retrieval
scores that motivated this entry.

## T6 toy world model — tabular only

`t6_world_model.py` uses a tabular count-based model. This saturates on
tiny state spaces and says nothing about deep world models. The T6
learning curve (in `docs/research/T6_WORLD_MODEL_RESULTS.md`) is a clean
measurement of *this* toy, not of world models in general.



## Recording-layer defects (added 2026-10-27)

Six defects found during the paper audit. Three independently masked the
placeholder failure — a trajectory with dropped tool arguments looks
sequence-correct.

| # | Defect | Fixed |
|---|---|---|
| 1 | tool args dropped before persistence | yes |
| 2 | observation truncated at 32 chars | yes |
| 3 | write content not persisted | yes |
| 4 | A/B probe paired item with itself (0.500 was noise) | yes |
| 5 | read/write target alias collapse | no |
| 6 | truncation at JSONL boundary drops step | no |

Defects 1–3 are the reason earlier verifier measurements measured the
recording layer, not the verifier. See `scripts/masking_ablation.py` for
the per-defect sensitivity measurement.
