# Scoped results and non-promotion

`chain-neutral.result.v0` contains `proof_validity`, `anchor_assurance`, `reason`, and a native profile/status/reason projection. `adapter.mjs --native` retains the complete original native result separately; vectors freeze the complete projected result.

Proof validity: VERIFIED means the supplied bounded inclusion relation passed under the selected policy; REFUTED means binding/proof/history contradicts the selected relation; UNVERIFIABLE means admission, selection or required evidence could not establish that relation. It is not a claim-wide aggregate, RVR recomputation status or authorization decision.

Anchor assurance: CHAIN_CONSISTENT means the supplied bounded historical relationship was checked; ANCHOR_UNCHECKED means no independently authenticated external anchoring was established. ANCHORED_VERIFIED is reserved for a future explicitly integrated timestamp verifier and is **never emitted in v0**. A structurally valid local proof can be VERIFIED/ANCHOR_UNCHECKED. A bad proof is REFUTED/ANCHOR_UNCHECKED, not VERIFIED merely because anchoring was not checked.

Missing policy is UNVERIFIABLE. A self-signed local checkpoint is not evidence of public authority. A claimed OTS confirmation is not timestamp verification. Optional timestamp absence does not refute a valid local inclusion; required absence prevents establishing the requested relation.

RVR's native `outcome` and `recomputationStatus` are retained in `rvr_boundary.py` outputs. They are never replaced by this projection.

```text
RECEIPT_INTEGRITY != ACTION_EXECUTION
SIGNED_DECISION != CORRECT_DECISION
INCLUSION != CLAIM_AUTHORIZATION
CONFORMANCE_PASS != EXECUTION_PERMISSION
```

Reporter process success means only that a report was emitted. Existing runner grading establishes conformance to the declared expected outputs. Missing expectation/report is REPORT_CONTRACT, genuine output mismatch is SUITE, unavailable runtime is RUNNER, and pin drift is DRIFT. No arbitrary stderr substring adds semantics here.
