# review profile deadline-derivation (v0.2) — follow-up to `review-profile-v0` / PR #6

Owned by **babyblueviper1** (invinoveritas). Deliberately a **separate PR from #6** (Pavlo's fix,
2026-08-02): the flat `response_deadline` formula is #6's real, current, frozen scope;
`request_class`-based deadline variation is real additional work and belongs stacked on top of
that frozen baseline, not folded into it. Does not modify `admission_check.py` or anything in
`../captured-admission-v0-review-profile/`.

    python3 deadline_derivation.py deadline_vectors.json   →  8/8

## What this adds

`response_deadline = accepted_at + Δ(policy_version, request_class)`, where `request_class`
buckets our real, live `artifact_type` (`core/models.py`, 11-valued `Literal`) using the exact
irreversible/reversible split already live in production
(`services/proof_signing.py`'s `IRREVERSIBLE_ARTIFACT_TYPES`) — not a new invented axis. `Δ`:
short=60s (the flat baseline from #6), long=180s — longer because irreversible-class review can
trigger the `reversibility_gate`'s extra confidence-floor check (`routes/inference.py`), real
additional processing, not an arbitrary bigger number.

## v0.2 — three corrections from Pavlo's second review (2026-08-02), all real

**1. Full-width sha256, not truncated.** v0.1's commitment hash truncated to 64 bits and the
README called it "real cryptographic evidence" a coincidence "can't" fool — a 64-bit truncation
has meaningful collision risk and must never be described as unfoolable. Fixed: full 256-bit hex
digest, no truncation.

**2. `unknown_policy_version` is distinct from `unknown_request_class`.** v0.1 collapsed "this
policy_version was never defined" and "this request_class isn't short/long within a real policy"
into one verdict. These are structurally different failures — a third party auditing a rejected
record needs to tell "the policy identity itself is bogus" apart from "the policy is real but this
bucket isn't." Two vectors below (`review_deadline_unknown_policy_version` vs.
`review_deadline_unknown_request_class`) exercise both, distinctly.

**3. One immutable, append-only table keyed by `policy_version` — the actual non-retroactivity fix.**
v0.1's real bug: both the old and new SLA deltas reused the SAME `policy_version` string
(`invinoveritas.review.v5`), which makes `policy_version` silently mutable and leaves "which table
resolves an old record" outside the record entirely — exactly what Pavlo's first non-retroactivity
point was about (a mismatch was only ever *detected*, never actually *validated correctly* against
its own history). Fixed the honest way, reusing the SAME discipline our own live
`REVIEW_POLICY_VERSION` already follows (`services/proof_signing.py`: "bump this when the review
contract/rubric changes... a past decision_ref always recomputes correctly against the rubric that
was actually in force") — an SLA-delta change is a rubric change, so it gets its own new
`policy_version`, appended to the same table, never overwriting the old entry. A record declaring
an old `policy_version` is looked up under exactly that key, forever; there is no "current table"
concept to accidentally apply to it.

`invinoveritas.review.v4` is used below as the illustrative prior version, matching the real
v2/v3/v4/v5 progression already documented in `proof_signing.py` — v4 itself never had a real SLA
table in production; this demonstrates the mechanism honestly, not a historical fact.

## The 8 vectors

- 2 positive baseline (short/long class under the current policy)
- 1 supplied-deadline-differs-from-derived
- 1 unknown `request_class` (real policy, bad bucket)
- 1 unknown `policy_version` (bad policy identity) — **new in v0.2**
- 1 `request_class` changed after capture/admission binding
- 1 **positive** non-retroactivity: an admission bound under the PRIOR policy (`v4`) resolves
  correctly against v4's own table entry — **new in v0.2, the vector v0.1 was actually missing**
- 1 negative: the SAME v4-bound admission, but with a reinterpretation attempt (deadline/commitment
  computed under v5's numbers instead) — caught at the full-width commitment check

Grep-verified before writing this: no timeout/SLA constant for `/review` exists in `core/models.py`
or `app.py` today — both `Δ` values are new, proposed numbers, open to revision once real values
are committed to production. Still proposed shape only. No production endpoint touched.
