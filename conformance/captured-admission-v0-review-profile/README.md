# review profile (v0) — over `captured-admission.v0`

Owned by **babyblueviper1** (invinoveritas), per the assignment in the `trustless-ai` working
group (2026-08-02): review, settlement (Jimmy), and TEE-epoch (Jimmy/Pavlo) each own their
terminal vocabulary over the shared `captured-admission.v0` core in `../captured-admission-v0/`.
This directory adds **no new checker code** — it reuses `admission_check.py` from the core
unmodified (`suite.json` pins its sha256), which is the point of a profile-agnostic core: the
review domain only supplies data (`profile.permitted_dispositions`) and interpretation
(this README), never a forked evaluator.

    python3 ../captured-admission-v0/admission_check.py vectors.json   →  8/8

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

## `response_deadline` — proposed derivation, not live

`response_deadline = accepted_at + POLICY_SLA_SECONDS[policy_version]`,
`POLICY_SLA_SECONDS["invinoveritas.review.v5"] = 60`.

Deterministically derived per Pavlo's fix (2026-08-02: "not an arbitrary published number"), so the
deadline is itself recomputable from the admission record alone, not a side-channel value.
Grep-verified before writing this doc: no timeout/SLA constant for `/review` exists in `core/models.py`
or `app.py` today — 60s is a **new, proposed** number (generous relative to typical sub-10s
LLM-backed review latency), open to revision once a real value is committed to production.

## Open, still-unresolved (not glossed over)

- **Idempotency at the admission layer.** `/review` has no idempotency key today. A client-side
  retry after a slow/ambiguous response could plausibly cause two independent verdict-commits
  against the same `admission_index` — modeled here as `conflict` (see
  `review_double_disposition_conflict_retry_race`), which is the CORRECT terminal once it happens,
  but doesn't by itself prevent it. Preventing it is separate, real, un-scoped work.
- **`request_class`-based deadline variation.** The formula above derives `response_deadline` from
  `policy_version` alone, not from `artifact_type` or any other request dimension — a real
  simplification, not yet weighed against whether different artifact types warrant different SLAs.
