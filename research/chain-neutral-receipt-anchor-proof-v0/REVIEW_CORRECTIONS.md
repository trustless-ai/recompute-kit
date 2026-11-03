# Same-PR corrections to the db11904 self-review

**Research candidate. Not normative. Not production-ready. Independent review remains pending.**

This update stays in PR #85. Parent: `db119044a99a6297f3aae283dc15e928b195f551`; main/base: `b9d4fc13a7b945dc7030360f7d39fe7c8484bef3`. It closes three author self-review findings without changing frozen RVR, either external Merkle implementation, the canonical runner, existing conformance suites, or source identities. Prior captured evidence remains byte-identical.

## F1 — authenticated bytes must still satisfy log-identity admission

Previously, an envelope and correctly signed/selected laboratory policy both using `log_id: 7` returned VERIFIED/CHAIN_CONSISTENT. The declared envelope schema requires a nonempty string. The adapter now checks the policy and envelope values before comparing their identities or invoking native proof verification. Values reaching this check that are not nonempty strings return UNVERIFIABLE / LOG_IDENTITY_MALFORMED, with no native proof result. Earlier policy authentication/shape refusals retain their own reasons.

`NUMERIC_LOG_ID` preserves the valid subject, slot proof and checkpoint; only the laboratory log identifiers and consequent authenticated policy digest/signature change. The negative expected result is authored literally before execution. This is an admission correction, not evidence of a forged authority, invalid Merkle root accepted, or production vulnerability.

The focused test also covers seven malformed envelope values (null, false, zero, seven, empty array, object, and string) plus a separately authenticated numeric policy value with a valid envelope string. All eight require the complete refusal projection. A missing envelope log_id now follows the same admission refusal instead of a determinate identity mismatch. General missing-field admission is not redesigned by this patch.

## F2 — witness each policy-binding relation

The selected-policy and envelope-policy binding guards already existed and worked, but were not exercised by a distinguishing negative witness. Removing either source site preserved all 39 earlier vectors and 12 earlier tests, even with the checker correctly repinned in the disposable experiment.

Three added fixtures independently select these relations:

| Vector | Minimal variation | Expected result |
|---|---|---|
| POLICY_NOT_SELECTED | Different caller policy digest; valid signed policy unchanged | UNVERIFIABLE / POLICY_SELECTION_MISMATCH |
| POLICY_REF_WRONG | Different envelope policy_ref | UNVERIFIABLE / POLICY_BINDING_MISMATCH |
| POLICY_PROFILE_DIFFERENT | Correctly authenticated policy selecting the other proof profile | UNVERIFIABLE / POLICY_BINDING_MISMATCH |

The latter two disjuncts are physically mutated separately. All three mutants now produce a different complete report for their named witness, preserve all five positives and are refuted as SUITE by the unchanged canonical reporter grader. No stale pin, crash or missing result counts as a kill.

## F3 — assert the RVR scalar-order result

The old `scalar-key-domain` entry recorded bytes without comparing them. It was an observational entry among 15 named entries, not demonstrated enforcement. The boundary now requires literal UTF-8 hex:

```text
7b22ee8080223a6e756c6c2c22f09f9880223a6e756c6c7d
```

These are compact JSON bytes for U+E000 before U+1F600 in scalar order. They are not obtained from the implementation under test. A regression substitutes the reverse-order native result only for this input and requires the assertion to refuse it. Frozen native RVR source is never edited.

Physical removal of only this assertion restores the old false acceptance: the regression fails with `RuntimeError not raised`, one assertion failure and zero errors, while the ordinary native result remains byte-identical. Restoration passes in normal and Python -O. This assertion-removal control is reported separately from the 20 proof mutations; a process crash is not credited as a kill.

## Measured checks

- 43/43 complete vector results. Original 39 input/expected objects and complete results preserved.
- 5 VERIFIED / 18 REFUTED / 20 UNVERIFIABLE; 2 CHAIN_CONSISTENT / 41 ANCHOR_UNCHECKED. No ANCHORED_VERIFIED claim.
- 14 research tests in normal/repeat/-O; 15 native RVR boundary entries, with the scalar comparison now asserted.
- 20/20 targeted physical proof mutants KILLED; zero survived/crashed/not-covered/control failures. Five complete positive controls preserved.
- Four additions to the mutation inventory: log-id-admission, selected-policy, policy-reference, policy-proof-profile. Each executes once and has its own named killer. The earlier 16 results remain valid finite evidence, not exhaustive coverage.
- Five complete machine-output families byte-identical normal/repeat/-O. Timing stderr is not described as identical.
- Fresh canonical main/candidate stdout byte-identical: 46 PASS / 6 NOT RUN / 2 SKIPPED. Existing runner semantics and suites unchanged.
- Historical controls: 105 runner; 9 mutation-inventory, 15 nonempty, 14 ungradable, 7 scan-binding tests, the latter four normal/-O. Full replay: 31 commands, zero nonzero exits.
- A separate replay of the prior 36 adversarial probes preserves 34 full results. Only numeric and missing log_id change, intentionally, to UNVERIFIABLE / LOG_IDENTITY_MALFORMED.

Raw outputs, exact argv/exit records, full mutation original/replacement expressions and native witness reports are in `evidence/pr85-corrections/`. Its `removal.py` reproduces the physical scalar assertion removal in a disposable copy. The canonical suite does not automatically discover this research directory; the existing dedicated research workflow executes the updated tests. No CI invocation is removed or added.

## Scope retained

Only local research behavior, vectors, tests, current result documents and their existing pins change. External SOURCE_PINS and original slot vectors stay unchanged. No new generic verifier, RVR receipt, serializer, trust authority, deployment, or public timestamp verification is added.

Mechanism/profile cross-labels, inherited non-R slot-side handling and upstream draft freshness notification remain review questions outside these three corrections. Their admission rules are not silently changed. Independent public-log authenticity, OTS verification, action execution and authorization remain NOT_COVERED. The PR stays Draft for further review; these finite tests do not authorize merging or execution.
