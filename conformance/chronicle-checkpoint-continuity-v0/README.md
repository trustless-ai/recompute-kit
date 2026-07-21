# Chronicle Checkpoint Continuity v0 — independent implementation

A second, clean-room implementation of Pavlo's **pairwise checkpoint continuity** gate,
built to the kit's own rule: *conformant iff it reproduces every `expected` from the same
inputs — not iff it matches a reference SDK.*

- **Spec + vectors (the authority) — FINAL, hash-pinned:** [`pipavlo82/crystal-receipt`](https://github.com/pipavlo82/crystal-receipt) @ `28f0d2be`
  - `docs/CHRONICLE_CHECKPOINT_CONTINUITY_V0.md` — the gate spec
    · SHA-256 `280b6c8106e288f1c9db4535b85bb7ff04a52d4fa8507be27ed5903b80a14782`
  - `tests/fixtures/chronicle-checkpoint-continuity-v0.json` — the 19 normative vectors
    · SHA-256 `8fa6d5331fee156055088fa9ca69b7258e346ee84e8038ac9db1faa5cf23d3e1`
  - `docs/CHRONICLE.md` — base v0 root derivation + local-verify scope
  - Hashes are SHA-256 over the exact committed blob bytes; both recomputed and matched before build.
    The vendored `continuity-vectors.json` here is those exact bytes.
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

`continuity-vectors.json` is the final 19-vector normative set (hash `8fa6d533…`). It includes two
order-precedence vectors that pin the short-circuits the earlier set left to prose:

- `predecessor_ref_mismatch_with_wrong_sequence` → `predecessor_ref_mismatch`
  (ref comparison before sequence classification)
- `predecessor_shape_malformed_and_local_verify_failed` → `predecessor_shape_malformed`
  (predecessor shape before predecessor local-verify)

The first is the case originally proposed in #99, adopted here under the profile author's naming. The
second pins predecessor **shape → local-verify**. A third, adjacent boundary — predecessor
**local-verify → ref comparison** — is distinct (shape-before-local-verify does not imply
local-verify-before-ref) and is being added as a 20th vector in
[crystal-receipt#101](https://github.com/pipavlo82/crystal-receipt/pull/101). This copy stays pinned
to the 19-vector `8fa6d533…` hash until that lands and the author re-pins the fixture blob hash to the
20-vector set. This from-scratch gate reproduces all of them (20/20 on the pending set).

`chronicle-root-golden-vectors.json` is vendored so the canonicalization self-check runs
standalone. Both fixtures are Pavlo's; the upstream copies remain normative.

## Status

No divergence: an implementation with no sight of the reference source lands on the same output
for all 19 vectors, so the pairwise-continuity spec is unambiguous at this profile's scope. The
remaining belt-and-suspenders step — diffing raw outputs against the reference implementation
itself (not just the shared `expected`) — is deliberately deferred until after opening that
source, which stays closed until then. The same drill applies when the deferred cross-checkpoint
**monotonicity** rule + vectors land: reimplement blind, then diff.
