# captured-admission.v0 — one lifecycle spine: bounded authority or obligation

Three lifecycles the working group derived independently — **review verdict dispositions**, **contribution
settlement**, and **TEE attestation key-epochs** — turned out to be the same structural primitive:

> an **incentive-aligned party captures** evidence the processor can't control → the **processor admits**
> the exact captured object into an **enumerable index or epoch** under a declared **temporal bound** →
> every later claim/disposition references that admission, transitions are **append-only and recomputable**,
> and a missing/expired/conflicting outcome is **derived, not asserted**.

This profile pins the shared **core** as blind-diffable vectors. Domain **profiles** (review, settlement,
TEE-epoch) own their own terminal vocabularies on top; `admission_check.py` is profile-agnostic core only.
Greenlit 2026-08-02 with **pipavlo82** (Pavlo), **babyblueviper1** (Fede), and **Jimmy Shi**, then hardened
by their blind-diff. Run: `python3 admission_check.py vectors.json` → **21/21**.

## Admission is a gate; obligation vs authority

An admission first **gates**, then creates one of two things:

- **rejected_at_admission** — a rejection receipt referencing the `request_capture`, creating **no
  obligation**. It is an admission *outcome*, **not** a disposition over an obligation (Pavlo).
- **accepted** — emits an `admission_receipt` and **creates an obligation** (or a bounded authority epoch).

| admission kind | creates | resolution |
|---|---|---|
| **obligation** (review, settlement) | a duty to produce **exactly one** disposition for the admitted index | resolves to one permitted disposition; deadline-miss is a **liveness failure**, tracked *separately* from resolution |
| **authority** (TEE key-epoch) | **time-bounded authority** to issue claims | each claim resolves against the epoch **in force at the claim's own anchor time**; later expiry/revocation acts **forward only** |

## Two stored dimensions, separate namespaces — plus derived predicates

The failure this guards is a **timing or authority condition silently collapsing into a validity judgment**:

- `lifecycle_state` — authority/lifecycle: `active` / `expired` / `revoked` / `superseded`. A timing condition.
- `disposition` — a profile's permitted **semantic** completion over an admitted obligation. A validity judgment.
- **derived, never stored** — `absence` (⇒ `liveness_failure`) and `conflict` are *recomputed* from the
  enumerable sequence. `missing` is not a value anyone writes; it is
  `admitted ∧ window elapsed ∧ no valid completing disposition`.

## Semantic resolution and liveness are separate, recomputable facts

For an accepted obligation the verdict carries **two** independent facts and never collapses them:

- **semantic** — was a valid completing disposition committed? `resolved:<disp>` / `pending` / `unresolved`.
- **liveness** — was a valid disposition committed **by the deadline**? `met` / `late` / `liveness_failure` / `open`.

A **late** disposition resolves the obligation **without erasing the missed deadline**: `resolved:<disp>|late`
keeps both facts true (Pavlo). `liveness_failure` is a **fixed historical fact** — a later verdict cannot
rewrite it to on-time. Collapsing the two (flipping `liveness_failure` → `resolved` when a late verdict
lands) would rewrite history, which is exactly the failure the separation prevents.

`response_deadline` is **not** an HTTP/transport SLA. It is a protocol-level bound, ideally **deterministically
derived** from `accepted_at`, `policy_version`, and any declared request class, published in the
`admission_receipt`. Its precise semantic: *the earliest `as_of` at which an accepted obligation with no
valid referencing disposition recomputes to a `liveness_failure`*. For a synchronous processor the normal
path puts `accepted_at` and the disposition microseconds apart; the deadline matters only for the abnormal
path (accept-commit → crash/drop → `liveness_failure` after the bound → any later disposition recorded as
`late`, not as proof no breach occurred).

## Modes (what a third party recomputes)

| mode | recomputes | verdicts |
|---|---|---|
| `obligation` | resolve one admitted index at `eval_at` (semantic AND liveness) | `not_admitted:<why>` · `resolved:<disp>\|met` · `resolved:<disp>\|late` · `pending\|open` · `unresolved\|liveness_failure` · `conflict` · `invalid_admission` |
| `authority` | attribute one claim against the epoch in force at **its own anchor time** | `attributed` · `out_of_authority` · `invalid_admission` · `invalid_transition` · `conflict_transition` |
| `disposition` | one disposition's validity **in its declared class** | `disposition:<kind>` · `rejected:<kind>` |

## Transport-agnostic — sync is a zero-width window; profiles declare reachable states

The core does **not** assume asynchronous execution. A synchronous processor is the degenerate case where
`accepted_at` and the disposition fall at the same instant — a **zero-width obligation window**. A profile
declares its **reachable-state subset**; any state outside it is *unreachable-by-construction*, not dead
code (a synchronous reviewer with no withdrawal window marks `cancelled` unreachable rather than building a
path that can never fire). What forces a *separate* admission record is **not** async transport — it is the
**non-suppression** property: only a separately-committed accept turns a crash/drop between accept and
disposition into a per-request falsifiable gap, instead of "never asked."

## Core invariants each vector exercises

1. **exact capture→admission binding** — `admission.captured_object_hash == capture.object_hash`, else `invalid_admission`.
2. **admission is a gate** — `rejected_at_admission` creates no obligation; only `accepted` does.
3. **admission kind** — obligation vs authority, resolved differently and never interchanged.
4. **enumerable index / epoch identity** — a disposition/claim only counts if it references *this* index/epoch.
5. **temporal bound** — obligation `response_deadline` (protocol-derived); authority `expiry` or a revoke/supersede transition.
6. **append-only transitions** — a disposition before `admitted_at`, or a transition for another epoch, does not count.
7. **anchor-time resolution** — authority claims judged by the claim's own anchor time against immutable history.
8. **non-retroactivity** — a later expiry/revoke/supersede never rewrites a claim in force when anchored; a late verdict never erases a deadline breach.
9. **derived absence & conflict** — recomputed, kept distinct from any semantic rejection.
10. **semantic ⟂ liveness ⟂ lifecycle** — the three dimensions stay in separate namespaces.

## Negative controls (they exercise the separations, not assert them)

- **NC1** — an overdue, unresolved obligation recomputes to `unresolved|liveness_failure`, **not** `rejected`
  (timing is not validity; NC1b: even an *invalid* disposition present doesn't turn it into a rejection).
- **NC2** — a claim anchored while an epoch was active stays `attributed` even after the epoch later
  `expired` / `revoked` / `superseded`; only claims anchored **after** the transition are `out_of_authority`.
- **NC3** — a disposition whose own predicate fails rejects **as its declared kind** (`rejected:verdict_published`),
  never relabelled (NC3b: a non-permitted kind rejects as *itself*).
- **NC4** — a second disposition on a resolved index recomputes as `conflict`, not a silent overwrite.
- **NC5** — a **late** disposition recomputes to `resolved:<disp>|late`: semantically resolved **and** the
  deadline breach preserved, both facts, never collapsed into a clean `resolved`.

## Coverage status (post blind-diff, PR #5)

`N/N` reproduced is *cases pass*, not *space covered*. Added after Pavlo's blind-diff of `1308ffc`:

- **explicit `as_of` gates** — `as_of` is a first-class input; the *same* record recomputes
  `pending|open` → `unresolved|liveness_failure` → `resolved:<disp>|late` across `as_of`, so every verdict
  is a pure function of `(record, as_of)`, never an implicit "now."
- **open vocabulary** — a **settlement** profile (`{partial_settlement, final_settlement, dispute_hold, …}`)
  resolves over the same core, and a foreign kind (a review term) rejects in-class — the core hardcodes no
  vocabulary.
- **authority-transition negatives** — a terminal transition **before activation** is `invalid_transition`
  (append-only violation); two distinct terminal transitions are `conflict_transition`; a transition for
  another epoch is epoch-scoped and does not end this one.

**Still open, deferred to their design shape (not yet represented):** sequence-level **enumerability**
(complete-set recompute, monotonic index, gap-visible-not-served) and **capture-evidence provenance**
(capture controlled by the incentive-aligned party, independently committed). These are tracked on PR #5.

## Relationship to the shipped work

The disposition side reuses the **class-preservation discipline** proven in `pq-recovery-classes-v0`
(a predicate miss is `rejected` in its declared class, never relabelled) — **as a reference for the rule,
not the universal terminal vocabulary**. The authority side is the same **anchor-time resolution +
non-retroactivity** enforced live in `pq-key-binding-v0`. The genuinely new legs are **capture**
(incentive-aligned party commits out of the processor's control) and **admission** (the processor accepts
the exact object into the enumerable sequence, or rejects it into a receipt that creates no obligation).

## Profiles (owned separately, not in this core)

- **review** — obligation completion set `{verdict_published, cancelled (only with a real withdrawal path),
  failed_with_reason}`; `rejected_at_admission` sits at the admission gate; `cancelled`/`expired` are
  unreachable-by-construction for a purely synchronous reviewer.
- **settlement** — partial / final settlement / dispute-hold / cancellation / expiry.
- **TEE-epoch** — active / revoked / expired / superseded, with outputs bound to the active epoch.

A profile may **not** collapse `missing`, `expired`, `revoked`, and `rejected` into one flat terminal set.
