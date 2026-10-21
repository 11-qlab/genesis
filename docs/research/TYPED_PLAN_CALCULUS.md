# Typed Plan Calculus

See `src/agi/reasoning/types.py`, `typecheck.py`, `repair.py` for the code
that implements what follows.

## Types

    τ ∈ { Unit, Str, Int, Bool }

## Tool signatures

    fs_list       : (path: Str)                                → Str
    fs_read       : (path: Str)                                → Str
    fs_write      : (path: Str, content: Str, mode: Str)       → Unit
    memory_search : (query: Str, k: Int)                       → Str
    shell         : (command: Str, timeout_s: Int)             → Str

## Arg expressions

    e ::= v            -- literal (Str / Int / Bool)
        | $s.f         -- reference to step s's field f

    Field f ::= out    -- the step's declared return value
              | ok     -- a Bool flag indicating success

## Typing rules

    Γ ⊢ v : typeof(v)

    Γ ⊢ $s.f : τ   iff   Γ[(s, f)] = τ

    Γ ⊢ (id, tool, args) : τ_out
       iff  Σ[tool] = (p₁:τ₁, …, pₙ:τₙ) → τ_out
        ∧  args[pᵢ] type-checks in Γ against τᵢ  for each i
        ∧  id ∉ dom(Γ)

    Γ ⊢ [] : Γ

    Γ ⊢ s :: rest : Γ'
       iff  Γ ⊢ s : τ_out
        ∧   Γ ⊎ {(s.id, .out) : τ_out, (s.id, .ok) : Bool} ⊢ rest : Γ'

## Theorems

**Progress.** If Γ ⊢ P : Γ' and every tool in P is registered, then
either P is empty or P = s :: rest with s.tool ∈ Σ, s.id ∉ dom(Γ),
and s.args type-check in Γ.

*Proof.* By cases on the derivation. The `::` rule directly asserts
all three conditions on the head step. ∎

**Preservation.** If Γ ⊢ s :: rest : Γ' and s executes successfully
with return v : τ_s matching the annotation, then
Γ ⊎ {(s.id, .out) : τ_s, (s.id, .ok) : Bool} ⊢ rest : Γ'.

*Proof.* The second premise of the `::` rule is exactly that
extended-environment judgment. ∎

**No-undefined-references (corollary).** If Γ ⊢ P : Γ', then no
execution of P can fail due to an unresolved $s.f reference.

*Proof.* Any $s.f in a step's args must satisfy Γᵢ[(s, f)] = τ at that
point (by the ref rule), which means step s was type-checked before
this step and produced a field f. At runtime, the reference resolves. ∎

## What these theorems do not prevent

If a step's argument is a **literal string** — for example the string
`"{{s1.result[0].text}}"` — that is type `Str` and passes type checking.
Theorems cover the typed-reference fragment only.

The class of failure exposed by `task_chain.jsonl`'s `tc-09` is this
exact class: the model wrote a string that *looks* like a reference
but is not the typed-reference syntax. The typed-plan repair loop
nudges the model toward `$s1.out` by showing type errors; it does not
*force* the model to use typed references. Enforcing this requires
either (a) rejecting any plan arg whose literal string contains
`{{` or similar, or (b) requiring the model to declare which args are
references vs literals. Both are follow-up decisions.

## What this specific instantiation adds

Theorems of the shape Progress + Preservation are Wright-Felleisen
(1994). Nothing in the *math* is novel. What is specific to this
project:

1. Types come from **tool signatures**, not from a language spec.
2. The "program" is a **plan produced by an LLM**, untyped, at high
   volume.
3. Type errors are used as a **repair signal** in a bounded loop,
   rather than rejecting the program outright.
4. The repair prompt shows the model the *exact typed error*, not a
   generic "step failed."

Point 3 is where this is adjacent to but distinct from grammar-
constrained decoding: the checker runs **after generation**, on the
plan tree, and its output goes back to the model as a repair hint.
That specific combination does not appear in this codebase, and — as
far as I know without searching — is not a standard pattern in
LLM-agent frameworks.

## What it does not solve

Six items that remain genuinely open, in `OPEN_PROBLEMS.md`.
