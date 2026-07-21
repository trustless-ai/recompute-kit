# Chronicle Checkpoint Continuity v0 — independent implementation

A second, clean-room implementation of Pavlo's **pairwise checkpoint continuity** gate,
built to the kit's own rule: *conformant iff it reproduces every `expected` from the same
inputs — not iff it matches a reference SDK.*

- **Spec + vectors (the authority):** [`pipavlo82/crystal-receipt`](https://github.com/pipavlo82/crystal-receipt) @ `4ee5a8d0` (#98)
  - `docs/CHRONICLE_CHECKPOINT_CONTINUITY_V0.md` — the gate spec
  - `docs/CHRONICLE.md` — base v0 root derivation + local-verify scope
  - `tests/fixtures/chronicle-checkpoint-continuity-v0.json` — the vectors
- **Author of the profile + reference implementation:** Pavlo (`pipavlo82`).
- **This implementation:** independent, by TMerlini, built from the spec + vectors **only** —
  `crystal-receipt/src/**` was never opened. That keeps the two implementations genuinely
  independent, so agreement is evidence and disagreement localizes a bug or a spec ambiguity.

## Run

```bash
bun continuity_gate.ts
```

Expected:

```
canonicalization self-check (golden roots): 22/22 OK
...
=== 19/19 vectors agree with pinned expected ===
Independent implementation agrees with the fixture on every vector.
```

## What it derives independently

1. **Root** — `"sha256:" + sha256(canonicalize(...))`, where canonicalize is recursively
   key-sorted compact UTF-8 JSON over the canonical fields, with ref-arrays lexicographically
   sorted and output/annotation fields (`metadata`, `checkpoint_root`) excluded. The exact
   canonicalization was reverse-engineered by matching the **golden root vectors** (22/22),
   never read from source — including the unicode-id vector, which pins UTF-8 handling.
2. **Local verify** — recomputed root byte-equals the stored root **and** stored `entry_refs`
   are already in canonical order (the checkpoint-specific extra requirement). It independently
   flags exactly the checkpoints designed to fail — including `noncanonical_entry_refs`, where
   the root matches but the order doesn't.
3. **The gate** — the 8-step normative evaluation order verbatim, first-applicable-wins, with
   `predecessor_ref_mismatch` (ref comparison) strictly before sequence classification.

## Vectors

`continuity-vectors.json` = the 17 upstream base vectors **plus** the two order-precedence
co-occurrence vectors proposed in [crystal-receipt#99](https://github.com/pipavlo82/crystal-receipt/pull/99):

- `cooccur_ref_mismatch_precedes_sequence_gap` → `predecessor_ref_mismatch`
  (ref comparison, step 7, before sequence classification, step 8)
- `cooccur_predecessor_local_verify_fail_precedes_ref_mismatch` → `predecessor_local_verifier_failed`
  (predecessor local-verify, step 6, before ref comparison, step 7)

Those two pin the only order-dependent short-circuits the base 17 leave to prose. This
from-scratch gate reproduces their expected outputs, which independently corroborates the PR.

`chronicle-root-golden-vectors.json` is vendored so the canonicalization self-check runs
standalone. Both fixtures are Pavlo's; the upstream copies remain normative.

## Status

No divergence: an implementation with no sight of the reference source lands on the same output
for all 19 vectors, so the pairwise-continuity spec is unambiguous at this profile's scope. The
remaining belt-and-suspenders step — diffing raw outputs against the reference implementation
itself (not just the shared `expected`) — is deliberately deferred until after opening that
source, which stays closed until then. The same drill applies when the deferred cross-checkpoint
**monotonicity** rule + vectors land: reimplement blind, then diff.
