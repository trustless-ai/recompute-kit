# Action subject record (not a verification receipt)

ID: `agent-action.subject-record.v0`. Exact keys:

```text
profile, canonicalization, phase, claim, subject, action, scope,
input, output, evidence, metadata
```

`profile` equals the ID above. `canonicalization` is the existing `receiptos.verify.canonical-json.v1`, reused from the pinned ReceiptOS strict parser/serializer. There is no new canonicalization engine or universal receipt format.

Each of claim/subject/action/scope/input/output is either null (not supplied) or exactly `{ "sha256": "<64 lowercase hex>" }`. These are commitments to exact opaque payload bytes, not semantic assertions by the verifier. `evidence` is an ordered array of the same commitment objects. `metadata` may contain values in the admitted byte domain; its content is committed but not interpreted as authority. `phase` is `pre_action` or `post_action_record`. Even a post-action **record** does not independently prove execution.

Admission: exact UTF-8, no BOM, maximum 4,194,304 bytes, at most 32 containers deep; inherited finite ReceiptOS resource limits, not a new ecosystem limit. Duplicate decoded members, invalid UTF-8, lone surrogates, unsafe numbers, negative zero, decimal/exponent spellings, non-ASCII keys, and the prototype names forbidden by the pinned parser are rejected. Integers span −9,007,199,254,740,991 through +9,007,199,254,740,991; values outside are not rounded. Strings contain Unicode scalar values and are not normalized.

Keys are printable nonempty ASCII, sorted lexicographically (UTF-16 and scalar order coincide in this restricted domain). Arrays preserve order and duplicates. Compact JSON uses exact standard string escapes and literal non-ASCII scalar values. No trailing LF. The parser's serialization **must equal the supplied bytes**; the adapter refuses non-canonical source bytes rather than silently normalizing them.

`subject_id = "0x" + lowercase_hex(SHA256(exact admitted source bytes))`.
No root field is excluded. The identity is carried outside this object. This differs deliberately from historical top-level `anchor` exclusion and from recompute-kit's historical two-field exclusion. Those profiles are not redefined.

RVR verification of this subject uses its exact bytes as an evidence payload. RVR's own descriptors, claims and results retain `rvr-canonical-json-v0`, which forbids numbers. See the explicit compatibility boundary and executable witnesses.
