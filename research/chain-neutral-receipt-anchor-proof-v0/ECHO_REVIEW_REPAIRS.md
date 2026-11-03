# Echo review: portability and selected-checkpoint evidence

Research candidate; not normative or production-ready. Same Draft PR #85, reviewed parent `1afc4ab3e3649e3d987d54006a3f3508c9fd159f`; original main/base `b9d4fc13a7b945dc7030360f7d39fe7c8484bef3`. [Echo's complete review](https://github.com/trustless-ai/recompute-kit/pull/85#issuecomment-6361707535) is independent upstream evidence. Executions below are author replays, not a new independent approval.

## Portability

The previous entry comparison mixed Node's resolved module URL with lexical argv. Actual WSL reproduction at the reviewed head: real path exit 0 with 9739 stdout bytes; directory symlink exit 0 with zero stdout bytes. This is an execution defect, not semantic refutation.

Both entry paths now use `realpathSync`, including `--preserve-symlinks-main`. Unresolvable paths and missing/empty serialized reports fail with exit 2. Programmatic import remains side-effect free. Linked-path tests cover full reports, empty-corpus refusal, physical removal of the realpath comparison, and restoration. Windows uses a real directory symlink when permitted (junction fallback is explicit); Linux uses an actual symbolic link. The removal restores exit 0 / empty stdout on the linked invocation while direct-path positives remain unchanged. No local macOS execution is claimed.

## Two checkpoint checks, two different witnesses

`SLOT_UNSELECTED_ROOT` preserves subject, policy and caller-selected checkpoint. Only the slot snapshot's informative `rules` header string changes, with header bytes and log_root recomputed consistently. The pinned slot specification says `rules` carries no rule of its own. Direct native-bridge execution establishes the altered inclusion and snapshot chain are internally valid. The envelope adapter nevertheless returns **REFUTED / CHECKPOINT_COMMITMENT_MISMATCH** before native execution (`native: null`).

The adapter additionally checks a VERIFIED bridge report's `log_root` against the selected checkpoint. A missing/malformed reported root is a process/report failure (exit 2), not a proved contradiction; a valid but different root is REFUTED. Native proof failures retain native reasons.

The two checks intentionally overlap:

- At the reviewed implementation, removing the envelope root comparison changes the new witness from REFUTED to VERIFIED. All original 43 cases still pass. This reproduces Echo's coverage finding.
- With the defensive check present, removing the early comparison still returns REFUTED. The full asserted result changes from `native: null` to an executed VERIFIED native result. The mutation is killed by this **evidence/execution-boundary assertion**, not by a false top-level acceptance. It is not a second verdict bypass.
- A separate disposable native-report fault changes only the bridge's returned root for an otherwise valid slot input. Correct adapter: REFUTED. Remove only the new native-root guard: VERIFIED. Restore: REFUTED. All ordinary corpus results remain unchanged with that fault absent. This is a component-boundary test, not a claim that the pinned upstream implementation produces an incorrect root.

No native Merkle, snapshot, signature or RVR algorithm is changed.

## Independently declared expectations

| Case | Protected relation | Expected validity / reason |
|---|---|---|
| SLOT_UNSELECTED_ROOT | Consistent proof still binds to selected checkpoint | REFUTED / CHECKPOINT_COMMITMENT_MISMATCH |
| POLICY_SCHEMA_WRONG | Accepted policy profile | UNVERIFIABLE / POLICY_PROFILE_UNSUPPORTED |
| POLICY_MECHANISM_UNKNOWN | Equal unknown mechanisms are not admission | UNVERIFIABLE / POLICY_SHAPE |
| ENVELOPE_MECHANISM_MISMATCH | Accepted mechanism matches policy | UNVERIFIABLE / ANCHOR_MECHANISM_UNSUPPORTED |
| POLICY_TIMESTAMP_NOT_BOOLEAN | Falsey integer zero is not boolean false | UNVERIFIABLE / POLICY_SHAPE |
| PROOF_SUPPLIED_CHECKPOINT_KEYS | Envelope keys cannot supply independent trust | UNVERIFIABLE / LOG_TRUST_ROOT_MISSING |

These literal expectations were authored before running the verifier. Every case has a unique ID and exact input commitments. Policy alterations are correctly signed laboratory fixtures with updated caller selection; failures do not depend on accidental signature mismatch. The key witness provides a usable key in untrusted envelope metadata while the authenticated policy provides no checkpoint key. Its mutation substitutes that untrusted key at the selection boundary. Existing `SELF_SUPPLIED_TRUST` separately protects policy-authority configuration.

## Counts and preservation

The reviewed source has **20** `MUTATIONS` entries plus a separately executed runtime-refusal removal control. Echo's reported 21 is not an invented 21-entry corpus inventory. All original entries/killers, 43 fixture objects/results, runtime control and scalar-order control remain preserved.

Current corpus: **49/49**, 5 VERIFIED / 19 REFUTED / 25 UNVERIFIABLE; 2 CHAIN_CONSISTENT / 47 ANCHOR_UNCHECKED. Physical corpus inventory: **26/26 KILLED**, zero SURVIVED / CRASHED / NOT_COVERED / control failures; five positives preserved. Five additions expose false acceptance; the sixth asserts the early native-evidence boundary above. Native-root and entrypoint removals are separately reported controls, not silently added to 26. CRASHED, NOT_APPLIED and equivalent-survivor sentinels remain non-kills.

Research tests: **18 methods**, including all original 14. `validate.py` runs normal/repeat/Python -O; `--historical` also executes the existing canonical and regression suites. Timing stderr is excluded from equality claims. Raw Windows/POSIX Python line endings are preserved; cross-platform parsed-JSON equality is separate from raw byte equality. Exact argv, outputs, source/input hashes and restoration records are in `evidence/echo-review/`. Earlier captured evidence stays unchanged.

## Scope and limits

Only research entry admission, defensive bridge-result binding, fixtures/tests, current documents and their existing pins change. Common runner, existing suites/workflows, ERC-8404 six-field receipt/status axes and external source pins remain unchanged. Newer upstream commits are not silently substituted for frozen ReceiptOS/invinoveritas versions.

Authority must still come from independently authenticated verifier configuration. Public authority provisioning, authenticated public-log publication, OTS verification, action execution and claim authorization remain NOT_COVERED. Mechanism-to-profile cross-label rules, inherited slot-side aliases and upstream spec-drift notification are not redesigned here. Keep Draft, no merge; request an independent cold replay, including Echo's macOS symlink environment.
