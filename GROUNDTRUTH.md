# Genesis ground truth — what it is, and how this pipeline verifies it

## The problem in the field

The 2026 survey "Autonomous Research Agents" found: *no LLM-era system demonstrates
an externally validated in-loop oracle under our coding rule.* Self-evaluation bias
dominates — plausible regressions get accepted as progress.

## What Genesis already has

Two functions in autonomous_research.py ARE a ground-truth oracle:

  _known_correct_for(cls, cand)  ->  reference implementation per class
  _baseline_for(cls, cand)       ->  stub that returns None per class

A test template is valid iff it produces a DISCRIMINATION:

  known_correct + test_ambiguous   ->  exit 0, prints PASS
  baseline      + test_ambiguous   ->  exit non-zero, assertion fires

If both hold, the test is a well-formed discriminator for that class.
If known_correct fails, the test is too strict or wrong.
If baseline passes, the test is too weak (accepts garbage).

That is the ground truth. It does not depend on an LLM judging an LLM.

## What this pipeline does

  10_extract_anchors.py    freezes anchor spec from TEMPLATES + references
  20_verify_anchors.py     EXECUTES each anchor, records discriminates/not
  30_anomaly_report.py     surfaces failures the taxonomy cannot explain
  40_paper_numbers.py      extracts paste-ready numbers from taxonomy + journal

## What it does NOT do

  - Does not generate new tests (that is the honest boundary; the gate exists,
    the generator is wired, no valid candidate has ever been accepted).
  - Does not modify taxonomy.json. Only 40_ reads it. Nothing writes it here.
  - Does not validate bench/families/seed/*.jsonl (that is the PTE track,
    a separate paper with its own expectations field).
  - Does not sandbox adversarially. subprocess.run(-I) + stripped env + 5s
    timeout stops accidents, not adversaries. RestrictedPython is the upgrade.

## The paper claim this supports

"Function signature activates canonical prior across model families" is a MODEL
claim already measured (450 trials, 0/25 vs 23/23). This pipeline establishes the
COMPLEMENTARY claim: the tests used to measure it are execution-verifiable
discriminators, not self-judged. Those two claims together are the paper.
