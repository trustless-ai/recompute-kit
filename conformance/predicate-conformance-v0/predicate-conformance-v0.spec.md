# predicate_conformance.v0 — recompute a PIN-RECORD flow: precommit → conformance-run → repair-run

**Profile:** `predicate_conformance.v0` · **Lane:** recomputable

Origin: the trustless-ai damon-group PIN-RECORD design thread (2026-08-17). The problem: proving
"a mutation-testing predicate was frozen before the gate ran against it, by an author disjoint
from whoever wrote the mutant" without letting any of those claims round up to something stronger
than what's actually checkable — the same discipline this repo already applies elsewhere
(`registered_mediator_evidence()`, `source_class` ladders, the collapsed-marker rule).

## The two immutable objects

**`predicate-precommit.v0`** — frozen *before* any run:

```json
{
  "record": "predicate-precommit.v0",
  "invariant":  { "definition_hash": "<sha256(JCS(frozen invariant definition))>" },
  "mutant":     { "id": "<m_i>", "hash": "<sha256(JCS(m_i content))>",
                  "author_commit": "<commit introducing m_i>", "author_identity": "<canonical author>" },
  "predicate":  { "attribution": { "canon_id": "canon.set.v0 | canon.sequence.v0 | canon.scalar.v0", "value": "<A_i>" },
                  "attribution_hash": "<sha256(JCS({canon_id, value: canonicalize(canon_id, A_i)})) | null if malformed>",
                  "oracle_author_commit": "<commit introducing A_i>", "oracle_author_identity": "<canonical author>" },
  "independence": { "claim": "disjoint_declared_identity",
                     "checked": "mutant.author_identity != predicate.oracle_author_identity",
                     "does_not_prove": "repository attribution (author_commit is never resolved against a real git repo — these are DECLARED strings the vector supplies, not git-verified authors), let alone person / control / toolchain independence — a checkable floor over declared data, strictly below anything real-repo-grounded." }
}
```

FIXED 2026-08-18 (Pavlo, PR #14 review, recomputed the head before flagging): the prior wording
claimed this proves "disjoint repository attribution" — overclaimed, since `author_identity` is a
declared string the vector supplies and `author_commit` is never resolved against a real git repo
by this gate. What's actually proved: the two DECLARED identity strings differ, nothing about the
underlying real authors. A real authorship check needs the same real-repo CI step C1 is deferred to.

Its own `sha256(JCS(record))` **is** `precommit_hash` — not a separate sub-object, so there is
exactly one hash to disagree about, ever. If `attribution_hash` is `null` (the declared `A_i` is
malformed — see canonicalization below), `precommit_hash` is also `null`: there is no valid
`predicate.attribution_hash` to fold into the record, so the precommit cannot be frozen at all.
Fails closed, never hashed around the gap.

**`predicate-conformance-run.v0`** — one per run:

```json
{
  "record": "predicate-conformance-run.v0",
  "consumes_precommit": "<the run's own BOUND claim about which precommit it consumed>",
  "gate_commit":  "<the gate IMPLEMENTATION commit this run consumed — bound, NOT the ancestry anchor; may predate the precommit>",
  "run_identity": "<the recorded/witnessed execution identity>",
  "observed_attribution": "<{ canon_id, value }, same declared shape as A_i>",
  "observed_hash": "<sha256(JCS({canon_id, value: canonicalize(canon_id, observed)})) | null if malformed>",
  "verdict": { "state": "PASS | CONFORMANCE_FAILED | UNRESOLVED",
               "reason": "<REQUIRED iff UNRESOLVED — no_predicate | malformed_predicate | no_observation | malformed_observation | precommit_not_consumed | gate_error | comparison_incomplete | other>" },
  "proves": "precommit existed before this recorded result",
  "does_not_prove": "that the gate was not executed or inspected earlier — that is an execution-witness / CI-provenance fact git ancestry cannot recover"
}
```

FIXED 2026-08-18 (Pavlo, PR #14 review, first round): `consumes_precommit` is now actually CHECKED,
not just documented — the gate recomputes `precommit_hash` fresh and compares it against
`run.consumes_precommit` BEFORE any attribution comparison happens (`reason: precommit_not_consumed`
if they don't match). A run that isn't correctly bound to the precommit it claims to consume cannot
produce a meaningful verdict, even if the underlying attributions would otherwise agree — the suite
now proves a bound run consumed the frozen precommit, not just that hash-comparison logic works in
isolation. Also fixed same pass: the `proves` line above said "before this RECORDED execution" —
record_identity (what this object supports) proves only `precommit_before_recorded_result`;
"execution" belongs exclusively to the stronger `execution_witness` claim below, and a record must
never borrow that word for the weaker claim it's actually making.

SCHEMA-COMPLETED 2026-08-18 (Pavlo, second review round: "the spec's predicate-conformance-run.v0
contains observed_hash and verdict, but the implemented ConformanceRun type contains neither...
'the specified run object is now mechanically constructed' still rounds up past what the
implementation builds"). Fair catch — the first-round fix built the binding CHECK correctly but
left the constructed object's own shape incomplete relative to this JSON example. `observed_hash`
and `verdict` are now real fields ON the constructed `ConformanceRun`/`RepairRun` object (see
`observedHash()` + the object-construction code in `evaluate()`), not values computed separately
and left off the record. `verdict` on the run object is the exact same value `evaluate()`'s own
top-level `conformance_verdict`/`repair_verdict` returns — one computation, attached in both
places it belongs, never two independent derivations that could drift out of sync.

`predicate-repair-run.v0` is the same shape, plus `repaired_mutant_commit`, for a post-repair
re-check — including the same `consumes_precommit` binding check. It is a **bound run that
recomputes**, never a stored `restores_observed_eq_Ai: true` fact — same class of fix as this
repo's `check_collapsed_states.py` targets (a marker that skips the recompute is the defect).

## The five CI invariants

- **C1 — precommit provenance.** Two mechanically distinct claims, not one (Merlini, 2026-08-17):
  a **record_identity** check (`precommit`-introducing commit is a git ancestor of
  `run.run_identity` — the weaker claim: the precommit *record* existed no later than this
  **recorded result**, nothing about execution) and an **execution_witness** check (an
  attestation/CI-provenance binding that the gate actually ran against that specific precommit —
  the stronger claim: this run genuinely witnessed that **execution**, not merely recorded a
  result after the fact). FIXED 2026-08-18 (Pavlo, PR #14 review): "execution" belongs exclusively
  to `execution_witness` — a DAG position cannot inherit execution provenance, so `record_identity`
  must never phrase its own (weaker) claim using that word, even loosely. A `record_identity`
  result asserting the stronger `execution_witness` claim fails closed rather than rounding up.
  **Both are out of scope for this gate/vectors fixture** — see below.
- **C2 — declared-identity disjointness.** `mutant.author_identity != predicate.oracle_author_identity`,
  checked mechanically over the DECLARED strings the vector supplies. FIXED 2026-08-18 (Pavlo, PR
  #14 review): the prior wording said this proves "disjoint repository attribution" — overclaimed,
  since `author_commit` is never resolved against a real git repo by this gate (structurally the
  same real-repo-dependent gap C1 already defers). The record's own `independence.does_not_prove`
  field now says so plainly, so the claim can never round up in transit.
- **C3 — hash recomputation, declared and versioned.** `mutant.hash` recomputes via
  `sha256(JCS(mutant content))`. `A_i` (and `observed`) is a **declared, versioned** value —
  `{ canon_id, value }` — and `canon_id` is itself part of the hash preimage
  (`sha256(JCS({canon_id, value: canonicalize(canon_id, value)}))`), so a change of
  canonicalization rule is a change of hash, never a silent re-canonicalization of old records
  under a new rule:
  - `canon.set.v0` — `value` MUST be an array with **no duplicate members** (by JCS-byte
    identity). A duplicate-bearing value is **MALFORMED**, not deduped — silently dropping the
    duplicate would hide the exact defect (whoever produced this "set" isn't actually emitting
    one) the same way folding distinct causes into one marker string does. A well-formed set is
    sorted by JCS-byte order before hashing (member order is not semantic for a real set).
  - `canon.sequence.v0` — `value` MUST be an array; order **is** semantic, duplicates allowed, no
    sort.
  - `canon.scalar.v0` — `value` MUST be **non-array**, JCS'd directly. FIXED 2026-08-18 (Pavlo, PR
    #14 review): the spec always said non-array, but the implementation previously fell through
    and silently accepted an array here too — a real spec/code mismatch, now rejected with the
    same fail-closed discipline as `set.v0`/`sequence.v0`'s own shape checks.
  `precommit_hash = sha256(JCS(the whole predicate-precommit.v0 record))`, not a delimiter-free
  concatenation of child fields (see the "why naive concatenation is wrong" section below).
- **C4 — verdict enum, four distinct UNRESOLVED reasons for four distinct causes.**
  `state ∈ {PASS, CONFORMANCE_FAILED, UNRESOLVED}`; `reason` required iff `UNRESOLVED`. Disagreement
  (`A_i` and `observed` both well-formed and differ) and inability-to-determine (comparison could
  not complete) are **distinct terminal states with no merge path** — the same boundary this repo's
  collapsed-marker rule enforces everywhere else. FIXED 2026-08-18 (Pavlo, PR #14 review, a real
  finding: this rule's own implementation had collapsed two of its own causes): a malformed
  PREDICATE attribution (`malformed_predicate`) and a malformed OBSERVED attribution
  (`malformed_observation`) are now distinct reasons, not folded into one string — the prior version
  returned `malformed_predicate` for both, exactly the defect this whole thread's own rule exists
  to catch, now closed in the rule's own code. `precommit_not_consumed` is the fourth: a run whose
  bound `consumes_precommit` doesn't match the freshly recomputed `precommit_hash` (see the
  `predicate-conformance-run.v0` section above) — checked BEFORE the attribution comparison, since
  comparing against the wrong precommit's frozen predicate would be meaningless even if the byte
  comparison happened to succeed.
- **C5 — repair is a run.** `predicate-repair-run.v0` recomputes `observed_attribution` after
  repair and derives its own verdict by the same path as the original run — never a pre-asserted
  boolean.

## Why naive concatenation is the wrong construction (not a demonstrated collision)

The obvious first draft hashes the precommit as `sha256(invariant_hash + mutant_hash + attribution_hash + oracle_author_commit)`
— string concatenation, no delimiter.

CLAIM CORRECTED 2026-08-18 (Pavlo, PR #14 review, two rounds): the original framing called this a
live `a‖bc == ab‖c` delimiter-collision risk, reasoning that `oracle_author_commit`'s
variable length sitting next to fixed-width sha256 hex digests made the field boundary ambiguous.
Round one caught that `--tamper`'s own implementation had omitted `oracle_author_commit` from its
concatenation entirely, so that boundary was never actually exercised — fixed by including it.
Round two caught that including it still doesn't demonstrate a collision: the preimage is
`fixed64 ‖ fixed64 ‖ fixed64 ‖ variable_tail` — three SHA-256 hex fields of known, fixed length
(64 characters each), with the one variable-length field placed **last**. That arrangement is
always unambiguously parseable (split at byte 192, the remainder is `oracle_author_commit`) no
matter what bytes it contains — there is no live boundary ambiguity in this specific four-field
order. A genuine `a‖bc == ab‖c` collision needs either two adjacent variable-length fields, or a
variable-length field not pinned to a fixed position — neither is true here.

**The honest claim: this is a structured-commitment argument, not a demonstrated collision.**
Hashing the **structured JSON object** (`sha256(JCS(record))`), where braces/quotes/commas are
real, unambiguous delimiters, is the right construction **on principle** — the fix already in
production elsewhere in this ecosystem (`registered_mediator_evidence()`'s own
`registry_snapshot_sha256`) is the same one used here. It doesn't depend on the current field
count, order, or width holding forever: a future schema change (an inserted field, a second
variable-length field, a reordering) could reintroduce real ambiguity in a naive concatenation;
JCS-object hashing is immune to that class of risk by construction, not just today, by virtue of
never encoding field boundaries into raw byte adjacency at all. `--tamper` in the adapter computes
the concatenation method (now genuinely including `oracle_author_commit`) — every **well-formed**
vector's `precommit_hash` mismatches under it, confirming the two constructions aren't accidentally
equivalent, which is real and worth checking even though it isn't evidence of the specific
collision risk the original framing claimed. Malformed-attribution vectors correctly still match,
since neither method can hash a record that was never built (`null` under both).

## Two honest bounds

1. **C2 proves a floor, not the strong claim.** `disjointness_holds` mechanically confirms two
   *declared identity strings* differ — never resolved against a real git repo by this gate. It
   does not and cannot confirm even repository attribution, let alone that the two humans/agents
   behind those identities are actually different people, on different infrastructure, using
   different toolchains — the record says so in `independence.does_not_prove`, not left implicit.
2. **C1 (provenance, both its record_identity and execution_witness legs, AND resolving
   author_commit to a real git author for C2) is deliberately not checked here.** All are facts
   about repository/CI history — real git ancestry, a real attestation binding, a real
   commit-to-author lookup — not recoverable from these JSON records in isolation. Encoding any of
   them in a vectors-based gate would mean faking git/CI operations against synthetic ids
   (worthless) or silently narrowing the claim to "the vector *says* so" — exactly the
   unearned-trust shape C1 exists to close. They belong in a real CI step against a real repo, not
   this fixture — deferred together, not as separate gaps.

## Reproduce it yourself

```bash
bun gate.ts              # recompute every vector, diff against pinned expected
bun gate.ts --tamper     # recompute with the naive-concatenation method — well-formed vectors should mismatch
```
