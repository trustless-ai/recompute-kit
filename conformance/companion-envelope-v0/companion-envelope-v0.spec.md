# companion-envelope.v0 — the verdict commits to its companion

A per-attestation PQ **companion** signs the verdict's semantic core. Storing the companion as a lookup
(a column, an index) makes "the companion for this proof" whatever the producer serves — a redirectable
hint, not a commitment. This profile pins the commitment.

## Construction (constructs in one direction)

```
verdict_core_cc = sha256(JCS(core))
    core = { raw_input_hash, sanitization_pipeline_hash, input_hash,
             output_hash, manifest_hash, agent_id, registry }   # registry lowercased; absent fields = null
companion       = { signed_digest: verdict_core_cc, pq_pubkey, ml_dsa_signature }
companion_cc    = sha256(JCS(companion))
envelope        = { schema: "companion-envelope.v0", verdict_core_cc, companion_cc }
envelope_cc     = sha256(JCS(envelope))
```

The companion signs `verdict_core_cc` (the semantic core), never the envelope — so the envelope commits to
the companion, not the other way around, and the graph builds one direction only.

`JCS` is RFC 8785 (sorted keys, compact separators `,`/`:`, literal non-ASCII UTF-8).

## Resolution

To be **committed**, a companion MUST carry a **present** `content_address` that is **exactly**
`verdict_core_cc`. This is what proves the companion named *this* core.

- `content_address` **absent** → `"unresolved"`, `companion_cc` `null`. An absent content-address MUST NOT
  be accepted and back-filled with `signed_digest = verdict_core_cc`: that would manufacture the binding for
  a companion that never named this core, and it would read as committed.
- `content_address` **present but ≠ `verdict_core_cc`** → `"unresolved"`, `companion_cc` `null` (it signed a
  different core).
- An **absent** companion is likewise `"unresolved"`, `companion_cc` `null`.
- An unresolvable companion MUST be **UNRESOLVED**, **never `false`** — "no companion here" and "the
  companion does not verify" are different claims a boolean cannot carry.

## Scope of `committed`

`committed` proves the envelope binds the **exact companion object** (this `pq_pubkey` + this
`ml_dsa_signature` over this `verdict_core_cc`). It does **NOT** assert that the ML-DSA signature
*verifies* — signature validity is a separate lane (the gateway's `signature_valid` / four-fact split),
not part of this profile unless signature verification is explicitly added to it.

## Conformance

`companion-envelope-v0.vectors.json` pins input `core`/`companion` → expected `verdict_core_cc`,
`companion_cc`, `companion_status`, `envelope_cc`. Conformance is exact reproduction. The set includes a
second committed companion whose only difference is its signature, whose `companion_cc` MUST differ (the
envelope commits the *exact* companion), plus the wrong-core and absence cases that MUST resolve to
`unresolved`. The gateway producer (`pqAgent.ts companionEnvelope`) and this gate reproduce identical bytes.
