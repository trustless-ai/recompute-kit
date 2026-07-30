# DEILS leg-2 — held-content-behind-commitment reveal check (our independent checker)

DEILS "leg 2" is Merlini's (trustless-ai) held-content-behind-commitment design: **existence** (a
`commitment_hash` + a monotonic ledger position) is mandatory-public and non-suppressible; **content** is
optional-private, held server-side and bound to the already-published commitment only when revealed.

`reveal_check.py` is **our** independent checker, derived from the rule alone —
`commitment_hash = "sha256:" + sha256(JCS(content)).hexdigest()`; a reveal recomputes over the revealed
content and binds iff equal; a null reveal is `content_withheld` (pending, not a failure); an unequal
recompute is `content_commitment_mismatch` (terminal, fail-closed). It does **not** read invinoveritas's
`check_deils_leg2.py` — the point is a **blind diff** of two implementations over the same vectors.

Reference implementation: invinoveritas `POST /prove {disclose:false}` + `POST /prove/{id}/reveal`.
Golden vectors (invinoveritas' own suite): `babyblueviper1/preaction-governance-conformance/examples/deils-leg2`.

    python3 reveal_check.py <vectors.json>

**Blind cross-recompute (2026-07-30): 5/5** against invinoveritas' pinned vectors — content_bound,
canonicalization_near_miss→bound, single_byte_flip→mismatch, content_withheld, and the
deep_nested_key_shuffle_adversarial case → bound. Two suites, two implementations, same verdicts.
