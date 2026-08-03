# review profile (v0) — over `captured-admission.v0`

Owned by **babyblueviper1** (invinoveritas), per the assignment in the `trustless-ai` working
group (2026-08-02): review, settlement (Jimmy), and TEE-epoch (Jimmy/Pavlo) each own their
terminal vocabulary over the shared `captured-admission.v0` core in `../captured-admission-v0/`.
This directory adds **no new checker code** — it reuses `admission_check.py` from the core
unmodified (`suite.json` pins its sha256), which is the point of a profile-agnostic core: the
review domain only supplies data (`profile.permitted_dispositions`) and interpretation
(this README), never a forked evaluator.

    python3 ../captured-admission-v0/admission_check.py vectors.json   →  10/10
    (8 mode=obligation + 2 mode=idempotency, same unmodified core checker for both)

## Status: proposed shape, not production

`/review` today has a disposition side only — `verdict` (approve / approve_with_concerns / reject),
`artifact_hash`, `policy_version`, all inside `decision_ref`'s signed preimage, published as
`proof.event` (Nostr-signed). That maps directly to this core's `resolved:verdict_published`.
**The entire admission leg does not exist in production**: no `request_capture_ref`, no
`admission_index`, no `accepted_at`, no `response_deadline`. Every vector here shows what those
records *would* look like once built — none of it is live. No production endpoint has been
changed to produce this document.

## Completion set

`profile.permitted_dispositions = ["verdict_published", "failed_with_reason"]`

Note `verdict_published` covers **all three** of our real verdict values — the semantic verdict
(approve / approve_with_concerns / reject) lives inside the disposition's own payload, outside the
core's concern. The obligation is "did a disposition land," not "which verdict." `failed_with_reason`
is the honest terminal for a genuine processing failure (LLM call errors, provider timeout) —
distinct from `reject`, which means "reviewed and found unsound," not "couldn't review." Today, a
real processing failure either 500s with no persisted record or silently retries — indistinguishable
from a `reject` verdict. That's a real, current gap this profile is designed to close.

`rejected_at_admission` is **not** in the completion set — per Pavlo's fix (2026-08-02): admission
is a gate, not an obligation disposition. A malformed `artifact_type` today 422s with no record at
all; under this profile it becomes `not_admitted:rejected_at_admission`, a rejection receipt
referencing the `request_capture`, and no obligation is ever created.

## Reachable subset (per Merlini's "profiles carry a reachable subset" fix, 2026-08-02)

**Reachable:** `resolved:verdict_published|met`, `resolved:verdict_published|late`,
`resolved:failed_with_reason|met`, `resolved:failed_with_reason|late`,
`not_admitted:rejected_at_admission` (gate), `unresolved|liveness_failure`, `conflict`,
`invalid_admission`. `pending|open` is reachable only in theory — between accept-commit and
verdict-commit inside one HTTP call, microseconds wide — and unobservable in practice since no
`GET /review/{admission_index}` query endpoint exists to catch it mid-flight.

**Unreachable by construction:** `cancelled` — no requester-withdrawal path exists on `/review`
today (it's a single synchronous call; there's nothing pending to withdraw once it returns). Would
require a real async mode or a pre-verdict cancel endpoint, neither built, neither committed.

## Why `liveness_failure` is reachable at all under a synchronous transport

This is the fork Merlini posed and we took (2026-08-02 group thread): a synchronous HTTP call can
still carry two separate commitments — accept-commit, then verdict-commit, microseconds apart at
the commitment layer, transport unchanged. A crash, dropped connection, or the LLM call itself
throwing between those two commits is exactly the failure our own `/ledger`'s `completeness` block
already discloses statistically (raw-tape count vs. published count, 219 vs. 214 as of this
writing) — the admission leg turns "accepted and then silence" from a population-level statistical
discrepancy into a **per-request, falsifiable predicate**. That is the actual motivating case for
building this at all, not a hypothetical.

## `response_deadline` — proposed value, a TRUSTED profile input in this PR (not recomputed here)

Every vector below supplies `response_deadline = accepted_at + 60` for `invinoveritas.review.v5`.
Relabeled 2026-08-02 (Pavlo's mechanical correction): within **this** PR, `response_deadline` is a
trusted, asserted profile input, not a deterministic/recomputable property — nothing in this
directory independently re-derives it from a policy table. The actual recomputation lives one PR
up: **PR #7** (`review-profile-deadline-v0`) adds `deadline_derivation.py`, a profile-owned
pre-validator that checks a supplied `response_deadline`/`deadline_policy_commitment` against
`Δ(policy_version, request_class)` *before* a record reaches the shared obligation checker here.
This PR's vectors are consistent with what #7 would derive (60s, `invinoveritas.review.v5`,
`request_class=short`) but that consistency isn't mechanically enforced by anything in this
directory — #7 is what actually enforces it.

Grep-verified before writing this doc: no timeout/SLA constant for `/review` exists in
`core/models.py` or `app.py` today — 60s is a **new, proposed** number (generous relative to
typical sub-10s LLM-backed review latency), open to revision once a real value is committed to
production.

**`request_class`-based deadline variation moved to a separate follow-up PR** (Pavlo, 2026-08-02:
keep this PR as the frozen, auditable review-profile baseline; the deadline-by-request-class
pre-validator is real, additional scope and belongs in its own PR, not stacked on top of this one).
The flat formula above is this PR's actual, current baseline — not a placeholder.

## Idempotency at the admission layer — two distinct failure shapes (fixed 2026-08-02, Pavlo's blind-diff)

`/review` has no idempotency key at the admission layer today. Two genuinely different failure
shapes follow from that, and they need two different modes to test correctly — an earlier version
of this profile only modeled one of them:

- **`mode=obligation` — double disposition on ONE admission** (`review_double_disposition_conflict_retry_race`):
  two verdict-commits racing to complete the *same* `admission_index`. Correctly resolves to
  `conflict`, not a silent overwrite.
- **`mode=idempotency` — duplicate ADMISSION for the same capture** (`review_idempotency_retry_without_key_creates_duplicate_admission`):
  a client-side retry after a slow/ambiguous response causes the *same request_capture* to be
  admitted twice, as two *separate* admissions with different `admission_index` values. This is
  the failure shape Pavlo's review actually named — mechanically detectable because `admission_id`
  is derived (`H(profile_id||canonical_capture_ref)`), never a caller-chosen label: both records
  derive the identical `admission_id` but were assigned different indices, resolving to
  `idempotency_violation`.

Both are detected, not prevented — a real `lookup-or-create(admission_id)` construction path on
the admission side is separate, real, un-scoped work.
