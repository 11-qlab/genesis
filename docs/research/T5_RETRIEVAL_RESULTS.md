# T5 Episodic Memory — Retrieval Quality

**Measurement date:** 2026-10-20
**Code:** `src/agi/trajectories/t5_memory.py::EpisodicMemory.retrieve_similar`
**Corpus:** 5 hand-written past goals, all recorded as successful.
**Similarity:** Jaccard over lowercased word tokens (`[a-zA-Z][a-zA-Z0-9_]+`).

## Data

Corpus:
- `list the workspace`
- `list the files`
- `read the config file`
- `create a new file`
- `search memory for sandbox notes`

Queries and top-2 hits (similarity in parentheses):

| query | hit 1 | hit 2 |
| --- | --- | --- |
| `list everything` | `list the files` (0.25) | `list the workspace` (0.25) |
| `show me the files` | `list the files` (0.40) | `list the workspace` (0.17) |
| `config` | `read the config file` (0.25) | — |

## Honest interpretation

**What works:** the mechanism retrieves from the store, ranks by similarity,
and returns hits with a numeric score. The plumbing is correct.

**What does not work — Jaccard specifically:**

- `list everything` ties between the two "list the ..." entries. There is
  no distinction between `list the files` and `list the workspace` on
  word-level overlap alone.
- `config` is a single-word query. It happens to hit only one entry, but
  that's because the other entries don't contain `config`, not because
  the similarity is meaningful. `create a new file` scores 0.00 against
  `config` — correct on token overlap, meaningless semantically.
- A query like `show me the file listing` would produce similar scores
  to `show me the files` (word overlap) even though one is imperative and
  the other is descriptive. Jaccard does not model intent.

**The fix:** replace Jaccard with an embedding-based similarity. The
project already has `memory/embeddings.py` with `HashEmbedding` (still
lexical) and `OpenAICompatEmbedding` (needs a real embedding provider).
The HashEmbedding version would not solve this — it's a bag-of-words hash
sketch. Only a real embedding model (sentence-transformers, OpenAI
embeddings, or a local BGE model) would distinguish `list the files`
from `list the workspace` given the query `list everything`.

**What this episode is:** a working retrieval mechanism with a documented
weakness. Adding embeddings is a real change, testable by rerunning the
same three queries with real embeddings and seeing whether the top hit
changes.

## Recorded in KNOWN_ISSUES.md

The KNOWN_ISSUES entry now says: Jaccard retrieval on short goals produces
near-ties that are semantically arbitrary; embedding replacement is
tracked but not built.
