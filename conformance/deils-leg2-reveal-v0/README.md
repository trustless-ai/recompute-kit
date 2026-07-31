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
