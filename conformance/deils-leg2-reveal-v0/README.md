# DEILS leg-2 — held-content-behind-commitment reveal check (our independent checker)

DEILS "leg 2" is Merlini's (trustless-ai) held-content-behind-commitment design: **existence** (a
`commitment_hash` + a monotonic ledger position) is mandatory-public and non-suppressible; **content** is
optional-private, held server-side and bound to the already-published commitment only when revealed.

`reveal_check.py` is **our** independent checker, derived from the rule alone —
`commitment_hash = "sha256:" + sha256(JCS(parsed(content))).hexdigest()`, where the input to JCS is ALWAYS
the **parsed** (language-native) value, never the served wire encoding. A reveal recomputes over the
revealed content and binds iff equal; a null reveal is `content_withheld` (pending, not a failure); an
unequal recompute is `content_commitment_mismatch` (terminal, fail-closed). It does **not** read
invinoveritas's `check_deils_leg2.py` — the point is a **blind diff** of two implementations.

**Byte-domain / wire trap.** The commitment is over raw-UTF-8 JCS bytes (`ensure_ascii=False`); a relay
that re-serializes with a default `json.dumps` (`ensure_ascii=True`, `\uXXXX`-escaped) serves *different
bytes for the same logical content*. A checker that hashes the served wire string directly gets the wrong
digest. The checker is **two-sided** on such cases: canonicalize-then-hash must bind, AND hashing the
escaped wire bytes must NOT match. (Surfaced by Merlini's escaping catch on a live `/prove` response;
pinned as `escaped_non_ascii_wire_trap` + folded into the rule's own domain by pipavlo82/babyblueviper1,
2026-07-31.)

Reference implementation: invinoveritas `POST /prove {disclose:false}` + `POST /prove/{id}/reveal`.
Golden vectors (invinoveritas' own suite): `babyblueviper1/preaction-governance-conformance/examples/deils-leg2`.

    python3 reveal_check.py <vectors.json>

**Blind cross-recompute (2026-07-31): 6/6** against invinoveritas' updated pinned vectors (df019b2) —
content_bound · near-miss→bound · single_byte_flip→mismatch · content_withheld · deep_nested_shuffle→bound ·
**escaped_non_ascii_wire_trap** (two-sided: canonicalize binds AND wire-byte-hash≠commitment). Also
verified **live**, blind: the on-the-wire `proof_eac5…` response recomputed byte-exact to its
`commitment_hash` from the rule alone. Two suites, two implementations, same verdicts, neither importing
the other's code.

## The committed content is `proof_payload`, and the disclosure surface must serve exactly that

The commitment is over **`proof_payload` alone** — never the signature or ledger-event envelope that wraps
it. A signature can't be inside the content it signs, and the nostr-style `event` (its own id/pubkey/sig,
kind 30078) is the transport wrapper, not the content. So:

    committed content = proof_payload         (NOT proof_payload ∪ {signature, event})
    commitment_hash   = "sha256:" + sha256(JCS(proof_payload)).hexdigest()   # ensure_ascii=False

**Two real bugs of this exact class, both caught by recomputing from the primary artifact** (blind hit on
live invinoveritas records, 2026-07-31; records frozen in `invinoveritas_real_records_2026-07-31.json`,
vectors in `vectors_invinoveritas_blindhit.json`, run with `stored_commitment_hash` mode):

1. **Commit/store mismatch (invinoveritas fix, commit earlier that day).** `payload_json` stored
   `{proof_payload, signature}` merged, but `commitment_hash` was computed over `proof_payload` alone — so
   any revealer submitting the held content verbatim got a false, terminal `content_commitment_mismatch`.
   Independent recompute converged on this root cause from the bytes: `proof_b0ce6e66`'s stored commitment
   binds the **clean** projection, and only mismatches if you hash the envelope in — i.e. the commitment was
   never wrong, the pre-fix verifier's field projection was. Fix: `payload_json` stores exactly
   `proof_payload`; signature/event moved to a separate column.

2. **Disclosure-surface mismatch (invinoveritas commit `00209da`).** After (1), `GET /attestations/{id}`
   still merged `signature_type`/`event` back into the served `proof` at read time — so `hash(served proof)`
   did **not** bind verbatim; an independent auditor pulling the URL cold needed an out-of-band projection to
   land on the commitment. Same failure class, moved to the read surface. Fix (**option a**): serve exactly
   `proof_payload` as `proof`, authenticity data in a separate top-level `signature` field. Verified live +
   blind: `hash(GET …/proof_ba17ddf4)` == `commitment_hash` == `sha256:6211de06…`, **zero projection**.

**Conformance rule for any implementer:** the disclosure endpoint MUST serve exactly the committed
`proof_payload` as the hashable field, so `hash(served) == commitment_hash` **verbatim**. Signature/event
authenticity data belongs in a sibling field, never merged into the hashable content. `reveal_check.py`
takes an optional `stored_commitment_hash` per case to verify a recompute against a record's *own published*
commitment (not a recomputed one) — the mode used for these live blind hits.
