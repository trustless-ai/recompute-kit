# NOT_COVERED and limitations

- Independent public authority authentication/provisioning outside the caller's selected lab policy.
- Bitcoin/OpenTimestamps verification, timestamp finality, historical publication, global log equivocation detection or transparency gossip. ANCHORED_VERIFIED is not reachable in v0.
- Actual action execution, truthful claims, correct judgment, execution/payment authorization, replay/idempotency/exactly-once, production concurrency, CAS, transaction isolation or linearizability.
- A new normative RVR Verification Profile for these Merkle/policy relations. Only the existing generic byte-identity profile is reused; anchoring is not automatically RVR verification.
- General JCS support by the original slot implementation outside the wrapper's stated ASCII-key/safe-integer subset.
- Independent validation of every slot-log metadata constraint: the imported checker does not establish date/cutoff correspondence or that a recorded slot's receipt was historically issued. Positive fixtures use next-UTC-midnight cutoff and informative string rules. Their consistency is not authenticated civil time or timestamp verification.
- Tamper-proof runtime or TOCTOU protection against concurrent privileged source replacement. Exact sources are checked in an isolated, non-adversarial filesystem before execution; no production enforcement claim follows.
- Exhaustive malformed-proof/type/resource analysis and independent second implementations of both native Merkle protocols. Finite synthetic vectors and physical mutations are evidence, not completeness proof.
- Browser/Web Component integration, lens distribution-license resolution, deployment, external timestamp services and chain-specific backends.

The checker reports the first established refusal, retaining the native report where executed. It does not aggregate every independent fault in a malformed multi-fault envelope. Published results explicitly distinguish proposal tests, unchanged upstream evidence, environmental failures and absent verification.
