# captured-admission.v0 — one lifecycle spine: bounded authority or obligation

Three lifecycles the working group derived independently — **review verdict dispositions**, **contribution
settlement**, and **TEE attestation key-epochs** — turned out to be the same structural primitive:

> an **incentive-aligned party captures** evidence the processor can't control → the **processor admits**
> the exact captured object into an **enumerable index or epoch** under a declared **temporal bound** →
> every later claim/disposition references that admission, transitions are **append-only and recomputable**,
> and a missing/expired/conflicting outcome is **derived, not asserted**.

This profile pins the shared **core** as blind-diffable vectors. Domain **profiles** (review, settlement,
TEE-epoch) own their own terminal vocabularies on top; `admission_check.py` is profile-agnostic core only.
Greenlit 2026-08-02 with **pipavlo82** (Pavlo), **babyblueviper1** (Fede), and **Jimmy Shi**. Run:
`python3 admission_check.py vectors.json` → **21/21**.

## The distinction the core must preserve (Pavlo's guard)

An admission creates one of two things, and they must not be conflated:

| admission kind | creates | resolution |
|---|---|---|
| **obligation** (review, settlement) | a duty to produce **exactly one** disposition for the admitted index | every index eventually references one permitted disposition; overdue-and-unresolved is a **liveness failure**, never a rejection |
| **authority** (TEE key-epoch) | **time-bounded authority** to issue claims | each claim resolves against the epoch **in force at the claim's own anchor time**; later expiry/revocation acts **forward only** |

## Two stored dimensions, in separate namespaces — plus derived predicates

The failure this guards is a **timing or authority condition silently collapsing into a validity judgment**.
So the record keeps two *stored* dimensions apart, and never stores the rest:

- `lifecycle_state` — authority/lifecycle: `active` / `expired` / `revoked` / `superseded`. A timing condition.
- `disposition` — a profile's permitted **semantic** completion over an admitted obligation. A validity judgment.
- **derived, never stored** — `absence` (⇒ `liveness_failure`) and `conflict` are *recomputed* from the
  enumerable sequence. `missing` is not a value anyone writes; it is
  `admitted ∧ window elapsed ∧ no valid completing disposition`.

## Modes (what a third party recomputes)

| mode | recomputes | verdicts |
|---|---|---|
| `obligation` | resolve one admitted index at `eval_at` | `resolved:<disp>` · `pending` · `liveness_failure` · `conflict` · `invalid_admission` |
| `authority` | attribute one claim against the epoch in force at **its own anchor time** | `attributed` · `out_of_authority` · `invalid_admission` |
| `disposition` | one disposition's validity **in its declared class** | `disposition:<kind>` · `rejected:<kind>` |

## Core invariants each vector exercises

1. **exact capture→admission binding** — `admission.captured_object_hash == capture.object_hash`, else `invalid_admission`.
2. **admission kind** — obligation vs authority, resolved differently and never interchanged.
3. **enumerable index / epoch identity** — a disposition/claim only counts if it references *this* index/epoch.
4. **temporal bound** — obligation `response_deadline`; authority `expiry` (or a revoke/supersede transition).
5. **append-only transitions** — a disposition before `admitted_at`, or a transition for another epoch, does not count.
6. **anchor-time resolution** — authority claims judged by the claim's own anchor time against immutable history.
7. **non-retroactivity** — a later expiry/revoke/supersede never rewrites a claim that was in force when anchored.
8. **derived absence & conflict** — recomputed, kept distinct from any semantic rejection.
9. **lifecycle ≠ disposition** — the two dimensions stay in separate namespaces.

## Negative controls (they exercise the separations, not assert them)

- **NC1** — an overdue, unresolved obligation recomputes to `liveness_failure`, **not** `rejected`
  (timing is not validity; even an *invalid* disposition present doesn't turn it into a rejection — NC1b).
- **NC2** — a claim anchored while an epoch was active stays `attributed` even after the epoch later
  `expired` / `revoked` / `superseded`; only claims anchored **after** the transition are `out_of_authority`.
- **NC3** — a disposition whose own predicate fails rejects **as its declared kind**
  (`rejected:verdict_published`), never relabelled into a neighbouring kind (NC3b: a non-permitted kind
  rejects as *itself*, not as some permitted neighbour).
- **NC4** — a second disposition on a resolved index recomputes as `conflict`, not a silent overwrite.

## Relationship to the shipped work

The disposition side reuses the **class-preservation discipline** proven in `pq-recovery-classes-v0`
(a predicate miss is `rejected` in its declared class, never relabelled) — **as a reference for the rule,
not as the universal terminal vocabulary**. The authority side is the same **anchor-time resolution +
non-retroactivity** enforced live in `pq-key-binding-v0` (which key governs an artifact is fixed by the
artifact's anchor time; rotation/revocation act forward only). The genuinely new legs here are **capture**
(incentive-aligned party commits out of the processor's control) and **admission** (the processor accepts
the exact object into the enumerable sequence).

## Profiles (owned separately, not in this core)

- **review** — which dispositions satisfy a review obligation (verdict / admission-rejection / cancellation / expiry / execution-failure).
- **settlement** — partial / final settlement / dispute-hold / cancellation / expiry.
- **TEE-epoch** — active / revoked / expired / superseded, with outputs bound to the active epoch.

Each profile ships its own vector file over this same core; a profile may **not** collapse `missing`,
`expired`, `revoked`, and `rejected` into one flat terminal set.
