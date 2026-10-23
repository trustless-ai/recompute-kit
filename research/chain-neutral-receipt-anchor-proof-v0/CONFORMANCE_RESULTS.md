# Measured conformance results

SPECIFICATION CANDIDATE; not normative or production-ready. Audited base `b9d4fc13a7b945dc7030360f7d39fe7c8484bef3`. This is author-executed evidence with independently specified expected relations, not an independent-review approval.

## Same-PR corrections after self-review

Current replay: `evidence/pr85-corrections/replay/`, 31 commands, all exit 0.

- 43/43 complete vector results; all original 39 input/expected objects and their results are unchanged.
- Proof validity: 5 VERIFIED / 18 REFUTED / 20 UNVERIFIABLE; assurance: 2 CHAIN_CONSISTENT / 41 ANCHOR_UNCHECKED.
- 14 research tests normal/repeat/Python -O; 15 RVR entries now include a literal scalar-order assertion.
- 20/20 targeted physical proof mutations KILLED; zero survived/crashed/not-covered/control failures; five positives preserved.
- Separate scalar assertion removal: one expected assertion failure, zero errors; restoration passes normal and -O; native positive output unchanged. This is not added to the 20 proof-mutation count.
- 36 independent probes: 34 full results unchanged; numeric and missing log_id now explicitly UNVERIFIABLE / LOG_IDENTITY_MALFORMED.
- Five complete machine-output families are byte-identical normal/repeat/-O. Canonical remains 46 PASS / 6 NOT RUN / 2 SKIPPED, byte-identical to a fresh main run.
- Historical regression counts remain 105 runner, 9 inventory, 15 nonempty, 14 ungradable and 7 scan-binding; the last four normal/-O.

See [REVIEW_CORRECTIONS.md](REVIEW_CORRECTIONS.md) for the exact boundary and removal evidence. The earlier 15-control wording below included an unasserted scalar-order observation at db11904; the correction makes that comparison load-bearing. Earlier finite 16-mutation results remain historical facts, not an exhaustive-coverage claim. All prior evidence directories remain byte-identical.

## Original db11904 replay (retained history)

The final complete run is in `evidence/complete/`: 31 command executions, all exit 0, including the historical regressions. Its five full machine-output families match the preceding `evidence/verified/` run byte-for-byte. `evidence/runtime-environment.json` records actual runtime versions and the independent RFC8785 test dependency hashes.

- 39/39 complete vector results reproduced by the existing reporter grader.
- Proof validity: {'VERIFIED': 5, 'REFUTED': 18, 'UNVERIFIABLE': 16}.
- Anchor assurance: {'ANCHOR_UNCHECKED': 37, 'CHAIN_CONSISTENT': 2}; ANCHORED_VERIFIED is not established.
- 12 research tests per normal/repeat/Python -O mode.
- 15 native ERC-8404 boundary controls per mode; unchanged six-field receipt and profile digest `51f79442e96339ca45e9e6cc0c8232833efbee20e7480df00987dbc97da72948`.
- 16/16 physical semantic mutations KILLED; 0 SURVIVED/CRASHED/NOT_COVERED/CONTROL_FAILURE; five positive complete results preserved under every mutation.
- Separate process-refusal removal witness: usable-runtime complete results unchanged; removing only the execution-failure guard changes absent-runtime exit 2 to false per-case output/exit 0; restoration returns exit 2. This is NOT added to the semantic mutation kill count.
- All 21 recorded research command executions returned 0.
- Original slot corpus: 15/15 unchanged. Original RVR Core gate passes (13 canonical-byte vectors plus its native case/dependency/mutant checks).
- Five complete machine-output families (report, native, RVR boundary, mutations, reporter replay) are byte-identical normal/repeat/-O. Unittest timing stderr is not byte-identical and is not claimed to be.
- 137/137 declared SHA pin occurrences valid across existing suites plus this research manifest; 23 are in the new manifest. External bootstrap verifies 30 pinned source files.

## Historical non-regression

Main canonical baseline and candidate stdout are byte-identical: **46 PASS / 6 declared NOT RUN / 2 SKIPPED**, exit 0; SHA256 `1b943bda16f5b84ab4a4070bd8971fcda4c4cf5185ac3c28b4440cf07f505f39`. This does not count the separate research suite as part of the main auto-discovered inventory.

Runner unit tests: 105 passed. Nonempty mutation inventory: 9 normal / 9 -O. Self-grading completeness/nonempty: 15 normal / 15 -O. Ungradable expectations: 14 normal / 14 -O. Scan-binding regression: 7 normal / 7 -O; raw logs are retained in `evidence/verified/scan-*.stderr`. Existing source/workflows remain unchanged. The optional historical replay now invokes that exact scan regression filename and does not silently skip absent test files.

All 239 base kit files, 2229 ReceiptOS files, 395 invinoveritas files, 25 lens files and 75 RVR files were compared to exact Git archive bytes; no difference. See `evidence/preservation.json`. This includes the frozen RVR Core and original slot vectors.

## Preserved failures and limits

The initial baseline lacked `ethers`: two TEE checks were RUNNER/exit 2, not semantic failures. Installing the repository's declared dependencies produced the baseline above. Original raw logs are retained.

The first research integration attempt was NOT COVERED because rfc8785 and the imported runner module were not declared in the research runtime manifest. Correct declarations were added; no runner semantics were modified. `evidence/linux/summary.json` intentionally retains that non-green attempt.

Earlier development logs (`first`, `mutations-first`, `linux`, `final`, `release`, `candidate`) are diagnostic snapshots and are not the final source-replay claim. They predate some naming, runtime-refusal or fixture refinements. In particular the initial unpublished receipt label was retired after the explicit ERC-8404 boundary audit. Some early synthetic slot headers used placeholder cutoff/rules metadata; final fixtures use published next-UTC-midnight/string conventions. No historical upstream evidence was regenerated.

Windows checkout CRLF conversion initially changed working-file hashes; exact Git blob bytes restored the published source hashes. Local fresh clone indexes were refreshed, with no source/history change. Setup-only shell quoting, a missing local Python package and a text-writer locale error were diagnosed before the corresponding successful reruns; none is credited as a conformance witness.

Post-commit replay and GitHub CI cannot be self-hashed into this same commit. Their exact-commit evidence is delivered separately and by the dedicated workflow artifacts. No absent CI job is called green here.

## Complete finite matrix

| Case | Proof validity | Anchor assurance | Reason | Protected guarantee |
|---|---|---|---|---|
| A_VALID | VERIFIED | ANCHOR_UNCHECKED | BOUNDED_INCLUSION_VERIFIED | native count-bound binary Merkle inclusion |
| B_VALID_CHAIN | VERIFIED | CHAIN_CONSISTENT | BOUNDED_INCLUSION_VERIFIED | native slot inclusion and two snapshots |
| WRONG_RECEIPT | REFUTED | ANCHOR_UNCHECKED | RECEIPT_IDENTITY_MISMATCH | receipt identity |
| WRONG_LEAF | REFUTED | ANCHOR_UNCHECKED | RECEIPT_LOG_LEAF_MISMATCH | leaf binding |
| WRONG_ROOT | REFUTED | ANCHOR_UNCHECKED | MERKLE_INCLUSION_INVALID | root |
| CORRUPT_SIBLING | REFUTED | ANCHOR_UNCHECKED | MERKLE_INCLUSION_INVALID | path |
| WRONG_INDEX | REFUTED | ANCHOR_UNCHECKED | MERKLE_INCLUSION_INVALID | position |
| WRONG_COUNT | REFUTED | ANCHOR_UNCHECKED | CHECKPOINT_TREE_SIZE_MISMATCH | count |
| UNKNOWN_PROFILE | UNVERIFIABLE | ANCHOR_UNCHECKED | PROOF_PROFILE_UNSUPPORTED | dispatch |
| WRONG_LOG | REFUTED | ANCHOR_UNCHECKED | LOG_IDENTITY_MISMATCH | policy log |
| MISSING_POLICY | UNVERIFIABLE | ANCHOR_UNCHECKED | POLICY_MISSING | explicit policy required |
| SELF_SUPPLIED_TRUST | UNVERIFIABLE | ANCHOR_UNCHECKED | POLICY_AUTHORITY_UNKNOWN | proof cannot grant trust |
| BAD_POLICY_SIGNATURE | UNVERIFIABLE | ANCHOR_UNCHECKED | POLICY_SIGNATURE_INVALID | authenticate policy |
| WRONG_CHECKPOINT | REFUTED | ANCHOR_UNCHECKED | SELECTED_CHECKPOINT_MISMATCH | different valid signed checkpoint cannot substitute |
| CONFLICTING_HISTORY | REFUTED | ANCHOR_UNCHECKED | SLOT_CHAIN_INVALID | supplied history conflict |
| BROKEN_PREV_ROOT | REFUTED | ANCHOR_UNCHECKED | SLOT_CHAIN_INVALID | chain continuity despite valid current root |
| DROPPED_SLOT | REFUTED | ANCHOR_UNCHECKED | SLOT_CHAIN_INVALID | old slots preserved, even when current root republished |
| MODIFIED_HISTORY | REFUTED | ANCHOR_UNCHECKED | SLOT_CHAIN_INVALID | old slots preserved, even when current root republished |
| INVALID_CHECKPOINT_SIGNATURE | REFUTED | ANCHOR_UNCHECKED | CHECKPOINT_SIGNATURE_INVALID | checkpoint signature |
| MISSING_TIMESTAMP | UNVERIFIABLE | ANCHOR_UNCHECKED | TIMESTAMP_EVIDENCE_MISSING | required timestamp missing |
| UNANCHORED_VALID | VERIFIED | ANCHOR_UNCHECKED | BOUNDED_INCLUSION_VERIFIED | valid inclusion does not imply anchoring |
| CLAIMED_OTS | UNVERIFIABLE | ANCHOR_UNCHECKED | TIMESTAMP_VERIFIER_NOT_AVAILABLE | OTS label not verification |
| UNSUPPORTED_VERSION | UNVERIFIABLE | ANCHOR_UNCHECKED | PROOF_PROFILE_UNSUPPORTED | version |
| NON_CANONICAL | UNVERIFIABLE | ANCHOR_UNCHECKED | NON_CANONICAL_RECEIPT | raw canonical byte admission |
| MALFORMED_JSON | UNVERIFIABLE | ANCHOR_UNCHECKED | MALFORMED_JSON | malformed differs from refuted |
| DUPLICATE_MEMBER | UNVERIFIABLE | ANCHOR_UNCHECKED | DUPLICATE_JSON_KEY | duplicates before decoding |
| NEGATIVE_ZERO | UNVERIFIABLE | ANCHOR_UNCHECKED | UNSAFE_JSON_NUMBER | negative zero |
| UNSAFE_INTEGER | UNVERIFIABLE | ANCHOR_UNCHECKED | UNSAFE_JSON_NUMBER | safe integer upper boundary |
| LONE_SURROGATE | UNVERIFIABLE | ANCHOR_UNCHECKED | INVALID_UNICODE | Unicode scalar requirement |
| NON_ASCII_KEY | UNVERIFIABLE | ANCHOR_UNCHECKED | INVALID_JSON_KEY | bounded common key domain |
| INVALID_UTF8 | UNVERIFIABLE | ANCHOR_UNCHECKED | INVALID_UTF8 | raw UTF8 |
| OTHER_MERKLE_CONVENTION | REFUTED | ANCHOR_UNCHECKED | MERKLE_INCLUSION_INVALID | same leaf/siblings/count, only internal-pair convention changed |
| SLOT_WRONG_RECEIPT | REFUTED | ANCHOR_UNCHECKED | SLOT_RECEIPT_BINDING_MISMATCH | valid slot proof for a different receipt cannot substitute |
| VALID_PROOF_OTHER_RECEIPT | REFUTED | ANCHOR_UNCHECKED | RECEIPT_LOG_LEAF_MISMATCH | valid manifest proof for a different receipt cannot substitute |
| CHAIN_REQUIRED | UNVERIFIABLE | ANCHOR_UNCHECKED | CHAIN_EVIDENCE_MISSING | required chain |
| SLOT_WRONG_POSITION | REFUTED | ANCHOR_UNCHECKED | SLOT_POSITION_INVALID | full snapshot binds leaf position |
| SAFE_BOUNDARIES_UNICODE | VERIFIED | ANCHOR_UNCHECKED | BOUNDED_INCLUSION_VERIFIED | safe boundary, Unicode values and ordering |
| A_CHAIN_VALID | VERIFIED | CHAIN_CONSISTENT | BOUNDED_INCLUSION_VERIFIED | native count-bound full-manifest extension |
| A_CHAIN_CONFLICT | REFUTED | ANCHOR_UNCHECKED | CONSISTENCY_CHECKPOINT_CONFLICT | signed current checkpoint does not waive supplied history conflict |
| NUMERIC_LOG_ID | UNVERIFIABLE | ANCHOR_UNCHECKED | LOG_IDENTITY_MALFORMED | authenticated policy bytes do not waive the nonempty-string log identity contract |
| POLICY_NOT_SELECTED | UNVERIFIABLE | ANCHOR_UNCHECKED | POLICY_SELECTION_MISMATCH | a valid policy signature cannot replace caller-selected policy identity |
| POLICY_REF_WRONG | UNVERIFIABLE | ANCHOR_UNCHECKED | POLICY_BINDING_MISMATCH | envelope references the exact selected authenticated policy |
| POLICY_PROFILE_DIFFERENT | UNVERIFIABLE | ANCHOR_UNCHECKED | POLICY_BINDING_MISMATCH | authenticated policy selects the same proof profile as the envelope |

## Echo-review follow-up (parent 1afc4ab)

Current 49/49 vectors, 18 research tests per normal/repeat/-O, 26/26 corpus mutants; five positives preserved, no crashes/survivors/not-covered credited as kills. One new mutation asserts early native evidence rather than a verdict change. Native-checkpoint and symlink removals are separately executed controls. Original 43 complete native results are unchanged. Windows and actual WSL Linux research runs pass; canonical Linux baseline/candidate byte-identical: 46 PASS / 6 NOT RUN / 2 SKIPPED. Historical105/9/15/14/7 test families pass. Exact evidence and the intentional distinction between byte equality and cross-platform JSON equality are in evidence/echo-review/summary.json; see ECHO_REVIEW_REPAIRS.md. Earlier sections remain historical measurements, not overwritten results.
