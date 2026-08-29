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

- A companion whose recorded `content_address` is **not** this `verdict_core_cc` did not sign this verdict:
  it is **not committed**. `companion_cc` is `null`, `companion_status` is `"unresolved"`.
- An **absent** companion is likewise `"unresolved"`, `companion_cc` `null`.
- An unresolvable companion MUST be **UNRESOLVED**, **never `false`** — "no companion here" and "the
  companion does not verify" are different claims a boolean cannot carry.

## Conformance

`companion-envelope-v0.vectors.json` pins input `core`/`companion` → expected `verdict_core_cc`,
`companion_cc`, `companion_status`, `envelope_cc`. Conformance is exact reproduction. The set includes a
second committed companion whose only difference is its signature, whose `companion_cc` MUST differ (the
envelope commits the *exact* companion), plus the wrong-core and absence cases that MUST resolve to
`unresolved`. The gateway producer (`pqAgent.ts companionEnvelope`) and this gate reproduce identical bytes.
