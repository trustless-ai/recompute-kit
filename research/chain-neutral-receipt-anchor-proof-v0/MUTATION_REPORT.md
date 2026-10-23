# Physical mutation evidence

`mutations.py` applies each source replacement exactly once in a disposable copy. Native external source mutations are repinned only in that copy so DRIFT cannot masquerade as a semantic kill. Original sources are never overwritten. A fresh Node process is used per mutation; Python bytecode is disabled.

A KILL requires successful complete machine output, the named distinguishing witness, all five complete positive controls unchanged, and SUITE refutation by the existing reporter grader. Source restoration and a final complete baseline are checked. CRASHED, NOT_APPLIED, SURVIVED, TIMEOUT, malformed reports, missing coverage and control failures are separate. Test sentinels actually produce CRASHED / NOT_APPLIED / SURVIVED and assert they are not KILLED; zero mutation inventory is refused.

Final result: **16 KILLED / 0 SURVIVED / 0 CRASHED / 0 NOT_COVERED / 0 CONTROL_FAILURE**. These are finite targeted mutations, not exhaustive coverage.

| Mutation | Source | Required killer | Changed fields | Status |
|---|---|---|---|---|
| profile-selection | adapter.mjs | UNSUPPORTED_VERSION | native, proof_validity, reason | KILLED |
| subject-identity | adapter.mjs | WRONG_RECEIPT | native, proof_validity, reason | KILLED |
| policy-authentication | adapter.mjs | BAD_POLICY_SIGNATURE | native, proof_validity, reason | KILLED |
| policy-authority | adapter.mjs | SELF_SUPPLIED_TRUST | native, proof_validity, reason | KILLED |
| log-selection | adapter.mjs | WRONG_LOG | native, proof_validity, reason | KILLED |
| checkpoint-selection | adapter.mjs | WRONG_CHECKPOINT | native, proof_validity, reason | KILLED |
| slot-leaf-binding | adapter.mjs | SLOT_WRONG_RECEIPT | anchor_assurance, native, proof_validity, reason | KILLED |
| chain-required | adapter.mjs | CHAIN_REQUIRED | native, proof_validity, reason | KILLED |
| timestamp-evidence | adapter.mjs | CLAIMED_OTS | proof_validity, reason | KILLED |
| raw-admission | adapter.mjs | NON_CANONICAL | proof_validity, reason | KILLED |
| native-result | adapter.mjs | INVALID_CHECKPOINT_SIGNATURE | proof_validity, reason | KILLED |
| assurance-separation | adapter.mjs | CORRUPT_SIBLING | proof_validity | KILLED |
| case-attribution | adapter.mjs | WRONG_RECEIPT | native, proof_validity, reason | KILLED |
| manifest-leaf | external:receiptos/research/agent-action-browser-verify-v0/lib/anchor.mjs | VALID_PROOF_OTHER_RECEIPT | native, proof_validity, reason | KILLED |
| merkle-verification | external:receiptos/research/agent-action-browser-verify-v0/lib/anchor.mjs | CORRUPT_SIBLING | native, proof_validity, reason | KILLED |
| slot-chain-continuity | slot_bridge.py | BROKEN_PREV_ROOT | anchor_assurance, native, proof_validity, reason | KILLED |

Full original/replacement expressions, exact-once counts, native witness results, positive controls and restoration evidence: `evidence/verified/normal-mutations.stdout`. Repeated and -O outputs match exactly.

The raw-admission mutation is observed through a changed refusal relation; it is not described as an unsafe admission when another binding still rejects. No reason-only change is described as a verdict flip. The additional runtime-refusal removal test is a separately reported classification witness, not a crashed semantic mutant counted as killed.
