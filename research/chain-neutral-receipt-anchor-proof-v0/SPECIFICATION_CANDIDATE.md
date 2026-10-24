# Specification candidate: finite composition, v0

Status: research, non-normative, not production-ready. The terms MUST/MUST NOT below express proposed local conformance requirements, not changes to any existing standard.

1. Admit exact action subject bytes according to [RECEIPT_PROFILE](RECEIPT_PROFILE.md). The subject is not an RVR receipt.
2. Verify the explicit subject identity in the envelope against those bytes.
3. Authenticate the policy under an independently supplied caller authority and exact selected policy digest. Evidence cannot choose its own trusted authority.
4. Match the policy's subject profile, proof profile, log ID, mechanism and selected checkpoint.
5. Dispatch to the separately versioned native proof implementation; never mix Merkle conventions.
6. Preserve the native verdict, reason and full result. A bad inclusion or broken history is REFUTED, not a successful proof with lower assurance.
7. Refuse requested timestamp assurance when no authenticated timestamp verifier exists. A JSON claim of confirmation is not verification.
8. Report the versioned proof projection separately from RVR outcome/recomputation and from action execution/permission.

Required inputs are finite supplied bytes plus separately selected policy context. A missing/malformed input yields inability to establish the proposed proof, not claim refutation. When available well-formed evidence demonstrates a mismatch, the corresponding native or binding relation is refuted. This finite pipeline is fail-closed, not a complete multi-failure evidence aggregator; its first refusal may leave later dimensions unchecked.

Expected conformance results are authored in `define_vectors.mjs` without invoking any verifier. It constructs proofs with upstream producers and synthetic snapshot material, but never derives expected verdicts from checker output. `vectors.json` freezes inputs, input commitments and expected complete projections. The existing reporter grader compares every result. Unsupported evidence can be a correctly reproduced UNVERIFIABLE negative vector.

This proposal deliberately does **not** define a new RVR Verification Profile for Merkle or policy verification. Such a profile would need the existing ERC-8404 closure and normative dependency rules, not a new registry. The executable RVR integration reuses only `rvr-generic-sha256-equals-v0` to establish subject-byte identity.
