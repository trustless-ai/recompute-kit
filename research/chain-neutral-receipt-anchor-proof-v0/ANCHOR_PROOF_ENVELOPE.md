# Common optional anchor-proof envelope

ID: `chain-neutral.anchor-proof-envelope.v0`. The transport is strict UTF-8 JSON admitted by the pinned parser. Fixtures freeze its exact bytes; selected identities concern the explicit subject and checkpoint, not an invented universal envelope ID.

Required interpreted fields:

```text
profile = chain-neutral.anchor-proof-envelope.v0
subject_profile = agent-action.subject-record.v0
subject_id = 0x-prefixed lowercase SHA-256
proof_profile = receiptos.manifest-proof.v0 | invinoveritas.decision_receipt.slot_log.v1
log_id = nonempty string
checkpoint_id = proof-profile-specific lowercase SHA-256
anchor_mechanism = local-ed25519 | snapshot-digest
policy_ref = lowercase SHA-256 of the authenticated policy body
proof = native proof evidence
timestamp = null | supplied timestamp evidence
```

Additional transport members have no authority and are not interpreted. A control deliberately supplies `untrusted_authorities`; it cannot establish trust. Unknown profile versions fail closed.

The caller supplies the selected policy digest and accepted authority map separately from this envelope. The policy and its signature travel alongside it, but cannot authenticate themselves. Log identity is a policy-selected identifier; the slot protocol has no native authenticated log-ID field, so only the independently selected snapshot digest binds this external name.

Both the envelope and authenticated policy must supply a nonempty string log identity. Malformed values reaching this admission check produce UNVERIFIABLE / LOG_IDENTITY_MALFORMED before identity comparison or native proof execution. An earlier policy admission/signature refusal remains distinct. A signature authenticates policy bytes; it does not waive their type requirements.

ReceiptOS proof evidence includes its exact leaf record, native count/index/sibling proof and signed checkpoint; optional full-manifest consistency retains native semantics. Slot proof evidence includes the exact snapshot and optional previous snapshot bytes, native inclusion object, selected index and count. The bounded wrapper checks snapshot/index/count association as well as original native inclusion/chain checks.

There is no generic public timestamp verifier in v0. Non-null timestamp evidence is preserved in the input, but produces `TIMESTAMP_VERIFIER_NOT_AVAILABLE`. Null evidence with a policy requirement produces `TIMESTAMP_EVIDENCE_MISSING`. Neither produces ANCHORED_VERIFIED.

The envelope is not a seventh RVR receipt field, payment instruction, permission grant, or execution certificate.
