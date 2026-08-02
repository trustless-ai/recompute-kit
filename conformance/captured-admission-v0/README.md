# captured-admission.v0 — one lifecycle spine: bounded authority or obligation

Three lifecycles the working group derived independently — **review verdict dispositions**, **contribution
settlement**, and **TEE attestation key-epochs** — turned out to be the same structural primitive:

> an **incentive-aligned party captures** evidence the processor can't control → the **processor admits**
> the exact captured object into an **enumerable index or epoch** under a declared **temporal bound** →
> every later claim/disposition references that admission, transitions are **append-only and recomputable**,
> and a missing/expired/conflicting outcome is **derived, not asserted**.

This profile pins the shared **core** as blind-diffable vectors. Domain **profiles** (review, settlement,
TEE-epoch) own their terminal vocabularies on top; `admission_check.py` is profile-agnostic core only.
Greenlit 2026-08-02 with **pipavlo82** (Pavlo), **babyblueviper1** (Fede), and **Jimmy Shi**, then shaped by
Pavlo's blind-diff on PR #5 (the five control families + the core-vs-profile split). Run:
`python3 admission_check.py vectors.json` → **49/49**. `N/N` reproduced is *cases pass*, not proof of total
coverage; coverage is tracked by invariant, below.

## Core proves; profile/policy owns

**CORE** proves identity, timing, commitment, exact binding, ordering, continuity. **PROFILE/POLICY** owns
the vocabularies, which capturer roles count as the incentive-aligned party, and which external anchor
classes count as independent — resolved from profile-pinned evidence (`capture_policy_id`), **never** from
an issuer's self-declaration (no self-declared `independent: true`).

## Admission is a gate; obligation vs authority

- **rejected_at_admission** — a rejection receipt referencing the `request_capture`, creating **no
  obligation**. An admission *outcome*, not a disposition.
- **accepted** — mints an `admission_receipt` and creates an **obligation** or a bounded **authority** epoch.

| kind | creates | resolution |
|---|---|---|
| **obligation** (review, settlement) | a duty to produce one disposition | resolves to one permitted disposition; a deadline miss is a **liveness failure**, tracked separately |
| **authority** (TEE key-epoch) | time-bounded authority to issue claims | each claim resolves against the epoch in force at the claim's **own anchor time**; expiry/revocation act forward only |

## Explicit `as_of`; two stored dimensions; derived predicates

`as_of` is a **required** first-class input — a missing `as_of` yields a canonical structural result
(`as_of_required`), never a silent fallback. Every verdict is a pure function of `(record, as_of)`, and the
evaluator **ignores every event whose own commit/anchor time is later than `as_of`** (`disposition.at`,
`claim.anchor_time`, `transition.at` ≤ `as_of`) — a future record never affects an earlier snapshot. This is
enforced **structurally, before any validation**: authority derives `visible_transitions = {t : t.at ≤
as_of}` first and runs *all* kind/rollback/successor/conflict checks and boundary selection **only** over
that set, so a future transition can never change an earlier snapshot's verdict. A snapshot taken before the
record exists returns `admission_not_yet_visible` (`as_of < admitted_at`) or `epoch_not_yet_active`
(`as_of < activated_at`).

- `lifecycle_state` — authority: `active` / `expired` / `revoked` / `superseded`. A timing condition.
- `disposition` — a profile's permitted **semantic** completion. A validity judgment.
- **derived, never stored** — `absence` (⇒ `liveness_failure`) and `conflict`, recomputed from the sequence.

**Semantic ⟂ liveness.** For an accepted obligation the verdict carries two independent facts: *semantic*
(`resolved:<disp>` / `pending` / `unresolved`) and *liveness* (`met` / `late` / `liveness_failure` / `open`).
A **late** disposition is `resolved:<disp>|late` — resolved **and** the breach preserved; `liveness_failure`
is a fixed historical fact a later verdict can never rewrite to on-time.

`response_deadline` is not a transport SLA — it is a protocol-level bound, deterministically derived from
`accepted_at` + `policy_version` + request class, published in the admission receipt: the earliest `as_of`
at which an accepted obligation with no valid disposition recomputes to `liveness_failure`.

## Modes (what a third party recomputes)

| mode | recomputes | verdicts |
|---|---|---|
| `obligation` | one admitted index at `as_of` (semantic AND liveness) | `as_of_required` · `admission_not_yet_visible` · `not_admitted:<why>` · `resolved:<disp>\|met` · `resolved:<disp>\|late` · `pending\|open` · `unresolved\|liveness_failure` · `conflict` · `invalid_admission` |
| `authority` | one claim vs the epoch in force at its own anchor time | `as_of_required` · `epoch_not_yet_active` · `attributed` · `out_of_authority` · `claim_not_yet_visible` · `invalid_admission` · `invalid_transition` · `transition_conflict` · `rollback_conflict` |
| `disposition` | one disposition's validity in its declared class | `disposition:<kind>` · `rejected:<kind>` · `unrecognized_disposition_kind` |
| `enumerate` | completeness/continuity of an anchored ordered sequence | `complete` · `gap:<i>` · `duplicate:<i>` · `conflicting_index:<i>` · `out_of_order` · `commitment_mismatch` · `invalid_sequence` |
| `capture` | capture-evidence provenance + exact binding into admission | `capture_admitted` · `capture_binding_mismatch` · `invalid_capture_signature` · `anchor_does_not_open` · `capture_anchored_after_admission` · `processor_signed_capture` · `capturer_not_incentive_aligned` · `unsupported_anchor_class` · `invalid_capture_timing` |
| `idempotency` | admission is idempotent on the capture; index stays monotonic | `admitted_ok` · `idempotent_replay` · `capture_id_conflict:<id>` · `idempotency_violation:<admission_id>` · `admission_id_not_derived` |

## The five control families (Pavlo's blind-diff, PR #5)

1. **explicit `as_of`** — one immutable history evaluated at three `as_of`: before deadline → `pending|open`;
   after deadline, before the late disposition is visible → `unresolved|liveness_failure`; after it →
   `resolved:<disp>|late`. Future events never reach back.
2. **open vocabulary** — a settlement profile resolves over the same core; a **recognized** kind that fails
   its predicate is `rejected:<declared-kind>` (class preserved), while a kind **outside** the declared
   vocabulary is `unrecognized_disposition_kind` — never `rejected:<input-string>`, which would let input
   extend the canonical output vocabulary. Class preservation applies only *after* structural admission.
3. **enumerability** — a sequence-level mode over an append-only hash chain with an independently anchored
   HEAD: index continuity, duplicates, gaps, out-of-order, conflicting commitments, head↔anchor consistency.
   Scope: this proves the admitted/published set is complete and continuous — **not** that every eligible
   object was admitted (that is the separate capture/non-suppression predicate). A Merkle root alone is not
   enumerable.
4. **capture provenance** — capture binds `{capture_id, captured_object_hash, capturer_identity, captured_at,
   signature, anchor_ref, anchor_class, anchor_time, anchor_commitment, capture_policy_id}`; admission binds
   the exact `capture_id` + hash. Core checks binding, signature, anchor-opens-to-record, and
   `anchor_time ≤ accepted_at`; **policy** checks the capturer is an acceptable incentive-aligned role and
   the anchor class is acceptably independent.
5. **authority transitions** — `expiry > activated_at`; terminal `transition.at ≥ activated_at`; unrecognized
   kind → `invalid_transition`; a future transition is ignored at an earlier `as_of`; a terminal cannot roll
   back to active (`rollback_conflict`); competing terminals → `transition_conflict`.

## Idempotency — request identity vs sequence identity kept separate

Admission is idempotent on the capture, but `admission_index` is **not** content-derived — that would
conflate request identity with the monotonic enumerable position (Pavlo). Two identities:

- `admission_id = H(profile_id ‖ canonical_capture_ref)` — deterministic **request** identity;
- `admission_index` — a sequence position assigned **once** on first acceptance — monotonic **order** identity;
- the `admission_id → admission_index` mapping is **immutable**.

A retry carrying the same exact canonical capture returns the existing receipt + index (`idempotent_replay`),
never a second admission. A `capture_id` opening to different canonical content is `capture_id_conflict`; two
indices for one `admission_id` is `idempotency_violation`; a `capture_id` accepted as an arbitrary
requester-chosen label (not derived from the authenticated capture) is `admission_id_not_derived`.

This makes a duplicate admission **mechanically detectable** and pins the required idempotent construction —
`lookup-or-create(admission_id)`: return the existing receipt on retry, assign an index once. Actual
*prevention* lives in that admission-construction path, not in the checker: the vectors detect the violation
and pin the construction, they do not enforce atomicity at write time.

## Evidence boundary — what the checker is, and isn't

This checker is a **recomputable vector oracle**, not a live cryptographic verifier. Scope stated explicitly
so no claim is stronger than what it proves:

- **Non-cryptographic stand-ins.** `_h` is sha256 **truncated to 64 bits**; `_sig`, `_capcommit`,
  `_chain_head`, and `admission_id` are deterministic **non-cryptographic** functions, chosen so vectors are
  byte-reproducible cold. Production and the profiles MUST use real signature verification and full-width
  commitments — these are oracles, not security primitives.
- **Supplied anchor evidence.** `enumerate`'s `anchored_head` and `capture`'s `anchor_commitment` are
  **supplied test-oracle values**. The checker verifies *internal* consistency (head matches the recomputed
  chain; commitment opens to the complete record) but does **not resolve a live external anchor**. "The
  anchor existed independently of the processor" is a profile/production resolution, out of scope here.
- **Enforced now:** the capture commitment binds the **complete** declared capture record, and
  `captured_at ≤ anchor_time ≤ accepted_at` is checked.

So this commit is **feature-frozen** with the evidence claims narrowed to exactly what the oracle proves —
"core-complete" meaning the invariant surface is complete and honestly scoped, not that the checker performs
cryptographic verification.

## Relationship to the shipped work

The disposition side reuses the **class-preservation discipline** from `pq-recovery-classes-v0` (a predicate
miss rejects in its declared class) — as a reference for the *rule*, not the universal vocabulary. The
authority side is the **anchor-time resolution + non-retroactivity** enforced live in `pq-key-binding-v0`.
The new legs are **capture** (incentive-aligned party commits out of the processor's control) and
**admission** (accept into the enumerable sequence, or reject into a receipt that creates no obligation).

## Profiles (owned separately, not in this core)

- **review** — completion set `{verdict_published, cancelled (only with a real withdrawal path),
  failed_with_reason}`; `rejected_at_admission` at the gate; `cancelled`/`expired` unreachable for a purely
  synchronous reviewer (declared, not dead code).
- **settlement** — `{partial_settlement, final_settlement, dispute_hold, cancelled, failed_with_reason}`.
- **TEE-epoch** — `active` / `revoked` / `expired` / `superseded`, outputs bound to the active epoch.

A profile may **not** collapse `missing`, `expired`, `revoked`, and `rejected` into one flat terminal set,
nor echo an input-controlled string into the canonical output vocabulary.
