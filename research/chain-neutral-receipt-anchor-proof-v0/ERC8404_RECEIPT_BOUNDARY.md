# ERC-8404 receipt boundary — research compatibility contract

**SPECIFICATION CANDIDATE. NOT NORMATIVE. Frozen ERC-8404/RVR Core is unchanged.**

## Exact authorities inspected

- ERC-8404 draft: `pipavlo82/ERCs@7a9e63a80bce04db53c6550103c1d41eca35f3d1`, `ERCS/erc-8404.md`, SHA-256 `63f1ad56b6a8a5099a12afbacd511c1271f50b1af6ef674a12b7aeb28850ad85`. Ethereum/ERCs PR 1980 remains a draft specification submission, not an adopted final standard.
- Executable RVR package: `pipavlo82/recomputable-verification-receipts@9dd36e882dd372f264b77b179130948aa5adcbde`.
- Existing generic Verification Profile: `rvr-generic-sha256-equals-v0`, native profile digest `51f79442e96339ca45e9e6cc0c8232833efbee20e7480df00987dbc97da72948`.
- Exact receipt schema: `conformance/rvr-v0/rvr.schema.json`, SHA-256 `97799403d8eb96c046930396c39e0f1c3e76d6c35fd0435937446ce844bd4dae`.
- Core thin-slice specification: `docs/spec/RECOMPUTABLE_VERIFICATION_RECEIPTS_V0.md`, SHA-256 `81077ddbf50624bc70941cf53a4f542604e926a653d7fcb3a36310ff5430b973`.

These source identities remain separate from older RC2 artifacts. No later semantics are backfilled onto old package identities. `SOURCE_PINS.json` identifies external, unchanged executable and specification bytes; it is a research source lock, **not** an RVR Verification Profile.

## Three objects, three responsibilities

| Object | Identity / role | Permitted conclusion |
|---|---|---|
| `agent-action.subject-record.v0` | SHA-256 of admitted exact subject-record bytes; `0x` + lowercase hex carrier | Identity of a declared action subject and commitments; no verification result or execution proof |
| Exact six-field ERC-8404 RVR | Four independently defined native RVR digest members; no new universal receipt ID is invented | Profile-defined verification outcome and a separate native recomputation result |
| `chain-neutral.anchor-proof-envelope.v0` | Selected subject reference and proof-profile-specific checkpoint commitment | Optional bounded commitment/inclusion proof under a separately authenticated verifier policy |

The earlier **unpublished working** label `agent-action.receipt-profile.v0` is retired in favor of `agent-action.subject-record.v0`. It was never a historical published profile. Existing `receiptos-c14n-v0`, `agent-action-receipt.v0`, `agent-action.receiptos-common-json.v0` and RVR identities are preserved.

An anchor envelope MUST NOT be inserted into the RVR receipt as a seventh field. A composition container may carry the three objects as siblings, with explicit identities. Removing an optional envelope does not alter a stored RVR receipt. If anchoring itself affects a verification claim, the chosen **RVR Verification Profile** must commit to the envelope and every relevant policy/trust input through its own closure; an uncommitted ambient policy cannot affect an RVR result.

## Exact RVR schema and native axes

The authoritative machine schema is the unchanged [pinned RVR schema](https://github.com/pipavlo82/recomputable-verification-receipts/blob/9dd36e882dd372f264b77b179130948aa5adcbde/conformance/rvr-v0/rvr.schema.json); its complete bytes are verified before the native schema gate executes. The new objects have separate exact machine schemas: [subject.schema.json](subject.schema.json) and [envelope.schema.json](envelope.schema.json), both pinned in `suite.json`. Those schemas do not redefine the RVR schema. Raw-byte admission and native proof checks add requirements that JSON Schema alone cannot express.

The receipt is exactly this object, with `additionalProperties: false`:

```text
{
  claimDigest: lowercase SHA-256 hex without prefix,
  evidenceSetDigest: lowercase SHA-256 hex without prefix,
  verificationProfileDigest: lowercase SHA-256 hex without prefix,
  outcome: VERIFIED | REFUTED | UNVERIFIABLE,
  reasonCode: member of the selected profile's verification namespace,
  resultDigest: lowercase SHA-256 hex without prefix
}
```

For the reused generic profile, the verification reasons are exactly `rvr.v0.digest_match`, `rvr.v0.digest_mismatch`, and `rvr.v0.required_evidence_unavailable`. Other RVR profiles have their own pinned namespaces; this experiment does not generalize those three reasons to all profiles.

Native recomputation separately returns `REPRODUCED`, `DIVERGED`, or `CANNOT_RECOMPUTE`. It is not a receipt field. `UNVERIFIABLE + REPRODUCED` is valid. Missing or mismatched required normative dependencies yield `CANNOT_RECOMPUTE` without evaluation; they are never converted to `REFUTED`, `DIVERGED`, or a new proof enum.

The anchor projection's `proof_validity` and `anchor_assurance` are **not these RVR axes**. Even identically spelled enum tokens carry their named relation and scope. No automatic conversion from `proof_validity=VERIFIED` to a generic RVR `outcome=VERIFIED`, `REPRODUCED`, action execution, or execution permission is defined.

## Canonical domains: reuse, not replacement

| Property | RVR identity-bearing objects | Action subject record / native ReceiptOS manifest |
|---|---|---|
| Existing byte contract | `rvr-canonical-json-v0` | `receiptos.verify.canonical-json.v1` |
| Implementation reused externally | RVR `adapter.py`: strict parser, `canonical_bytes`, native profile gate | ReceiptOS `src/core/strict-json.mjs` |
| Numbers | Forbidden; quantities use canonical unsigned decimal strings | Exact safe integers only, ±(2^53−1); `-0`, fractions/exponents rejected at raw admission |
| Object keys | Unicode scalar sequence order | Safe printable ASCII keys, UTF-16 sort (equivalent on admitted ASCII keys); dangerous prototype names excluded |
| Unicode values | Scalars, no normalization | Scalars, no normalization |
| Duplicate decoded members | Reject | Reject |
| Whitespace / LF | No insignificant whitespace | No insignificant whitespace; no trailing LF |
| Receipt root exclusions | None; identities defined by RVR object role | None; subject identity is outside subject bytes |

There is no new `chain-neutral.canonical-json.v0` serializer. The action subject's 4 MiB / 32-container admission bounds reuse the existing ReceiptOS implementation bounds as this finite research profile's limits; they are not universal RVR or ecosystem limits. RVR does not gain those limits.

Safe-integer subject bytes may be an RVR evidence **payload**: raw payloads are not RVR identity-bearing JSON. The evidence descriptor uses a decimal-string byte length and SHA-256 of exact raw bytes. It is invalid to parse such a subject and silently insert its numeric members into an RVR identity-bearing claim or profile. No conversion or normalization is implicit.

Positive byte intersection: `{"a":[true,null,"π"]}` has identical canonical bytes in both domains. Negative witnesses: `{"n":1}` is in the action byte domain but rejected by RVR canonicalization; non-ASCII object keys are admitted and scalar-sorted by RVR but refused by the selected ReceiptOS byte domain. A well-formed surrogate pair is a scalar; a lone surrogate and duplicate decoded key are refused by both. These witnesses are executable in `rvr_boundary.py`.

The scalar-order witness explicitly compares native bytes for U+E000 and U+1F600 keys with literal expected UTF-8 bytes, placing U+E000 first. It is not merely a recorded observation. `test_scalar_order_is_asserted` substitutes a wrong-order native result for this witness only and requires rejection. Removing just the comparison restores false acceptance and makes that regression fail; the frozen native RVR implementation is never edited.

## Verification Profile identity and dependency closure are reused intact

The native manifest, its bootstrap schema and profile-specific constraints, profile digest, claim and evidence identity, result identity and projections, dependency resolver, and recomputation procedure are directly reused. The adapter implementation is not added to RVR profile identity.

Resolution remains: explicit package root → resolve confined relative path → read bytes → match the committed SHA-256 → use those exact bytes. Every outcome-affecting dependency is normative. A `requiredForRecomputation=false` artifact cannot influence individual recomputation. Research source hashing and Git provenance do not replace this native closure.

## Executable interoperability

`rvr_boundary.py` uses the unchanged generic profile to verify **only**:

```text
SHA256_EQUALS(action-subject exact payload bytes, independently supplied expected digest)
```

It obtains the ordinary native six-field receipt and canonical result with the upstream API, then invokes native recomputation. The native expected outcomes in the controls are literal invariants, not read back from produced results. The subject's action/claim/scope commitments do not turn SHA256_EQUALS into action execution, claim truth, authorization, or reproduction of a nondeterministic decision. A stronger action claim needs its own existing or separately specified RVR Verification Profile. This experiment does not invent one by renaming the hash check.

| Witness | Required native result / boundary |
|---|---|
| Subject bytes equal independently supplied digest | `VERIFIED / REPRODUCED` |
| Expected digest differs | `REFUTED / REPRODUCED` for the stored negative result |
| Descriptor explicitly commits UNAVAILABLE | `UNVERIFIABLE / REPRODUCED` |
| Required specification unavailable | `CANNOT_RECOMPUTE`, `evaluationPerformed=false` |
| Required specification has wrong bytes | `CANNOT_RECOMPUTE`, no evaluation |
| Add anchor as seventh receipt member | Native schema gate rejects |
| Change stored outcome without canonical-result projection | Native projection gate rejects |
| Optional envelope removed | Native receipt/result identities unchanged |
| Subject payload has safe integers | Allowed as exact raw evidence, not as RVR identity-bearing JSON |

## Why not put everything into RVR?

There is no justification for a replacement verification receipt, serializer, profile registry, or dependency engine: those components **can and are directly reused**. The missing piece is a typed action **subject**, which RVR intentionally leaves profile/domain-specific, and two particular optional inclusion evidence formats. The existing generic SHA256_EQUALS profile cannot directly verify a Merkle path, authenticate a log policy, or prove an action executed. The existing RVR core is not modified to add these meanings. The exact native Merkle implementations remain external evidence checkers; their laboratory projection is not a newly certified RVR profile.

Before any future normative anchor Verification Profile is proposed, its exact proposition, policy authentication inputs, proof dependencies, canonical result, reason namespace and closure must be expressed using the **existing RVR manifest contract** and independently reviewed. This draft makes no claim that this further integration has already happened.
