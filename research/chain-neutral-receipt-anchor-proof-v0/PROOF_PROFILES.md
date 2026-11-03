# Two proof protocols, unchanged algorithms

## ReceiptOS manifest binding: `receiptos.manifest-proof.v0`

This proposed binding wraps existing `receiptos.verify.capsule-inclusion.v1` and the local research checkpoint `agent-action.local-manifest-log.v0` at the exact external commit in SOURCE_PINS.

Let D be ASCII `receiptos.verify.capsule-merkle.v1\0`. A leaf is SHA256(D || 00 || canonical(entry)); a pair is SHA256(D || 01 || binary(left_digest) || binary(right_digest)); root is SHA256(D || 02 || uint32be(count) || binary(top)). Odd nodes duplicate. Entry fields are exactly id/digest/size. The native verifier checks index/count/path direction, exact path length and odd-node duplication. Sorted manifest IDs and count limits remain native.

The existing subject-root binding consumes the **66 ASCII bytes** of `0x` + digest, not decoded 32 bytes, as a record: id `receipt/<hex>`, digest SHA256(66 bytes), size 66. The historical native `receipt/` namespace is preserved; the common envelope explicitly identifies an action subject, not RVR.

Checkpoint identity is SHA256(ASCII `agent-action.local-manifest-checkpoint.v0\0` || canonical(body)). Body includes schema/log_id/sequence/tree_size/merkle_root/previous_checkpoint_id. Ed25519 signs the same bytes. Key choice comes only from the authenticated policy. Existing full-manifest extension is a finite set-extension test, not CT consistency, global append-only enforcement or publication proof.

## Slot log: `invinoveritas.decision_receipt.slot_log.v1`

The original published profile is externally pinned: leaf SHA256(JCS(slot line)); pair SHA256(UTF8(left_hex + right_hex)); duplicate odd final node; log_root SHA256(JCS(header)); daily previous-root chaining. Header and each slot occupy a canonical JSONL line with LF, including the final line. Empty-tree seed is native, but selected inclusion requires an actual slot.

The original checker is executed, not translated into ReceiptOS hashing. The wrapper limits synthetic admitted slot values to safe integers/null/scalar strings/arrays/ASCII-key objects: this is an explicit subset avoiding the original Python serializer's non-ASCII-key/JCS mismatch, not a repair or claim of general RFC8785 equivalence. Optional OpenTimestamps authentication remains absent.

The receipt-to-slot mapping commits `claim_sha256` to canonical `{subject_profile, subject_id}`, with `scope=decider`. `decider_sig` remains an opaque original field; this profile does not authenticate it or infer the truth of a decider judgment. Snapshot selection is authenticated through policy. Original slot vectors remain unchanged and separate from these synthetic examples.
