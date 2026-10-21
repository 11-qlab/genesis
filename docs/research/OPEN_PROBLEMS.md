# Open Problems

Things this project does not solve, stated so that no one reading the
repo mistakes the typed-plan work for a solution.

## 1. String-vs-template ambiguity
A literal string like `"{{s1.out}}"` type-checks as `Str`. The type
checker cannot distinguish "this is data" from "this is a broken
attempt at a reference." Fix requires an explicit marker (e.g. args
must be either `{"$ref": "s1.out"}` or `{"$lit": "text"}` — no bare
strings), which changes the plan schema. Not implemented.

## 2. Semantic type compatibility
`fs_read` returns "file content" as `Str` and `fs_write` accepts
"content" as `Str`. Both are `Str`, so `fs_write("a.txt",
"$s1.out", "overwrite")` where `s1 = fs_read("b.txt")` type-checks
even if that wasn't the goal. Semantic sub-typing would require a
model of what each string *means*, which is beyond the current
architecture.

## 3. Plan revision
Typed repair fixes surface errors. A plan that type-checks but is
structurally wrong — wrong step count, wrong order of operations,
unnecessary steps — passes. Plan-level revision (rejecting and
replanning the whole plan, not just type errors) is not implemented.

## 4. Capability self-model
The system cannot say "I do not know how to do this." Every run
attempts a plan regardless of whether the model has any basis for
believing it will succeed.

## 5. Causal reasoning
A successful typed plan says nothing about *why* it worked. If a
step succeeded because a specific file existed, there is no
representation of that dependency.

## 6. Cross-run learning
Every run starts fresh. Nothing from run N informs run N+1.
Continual learning is not present.
