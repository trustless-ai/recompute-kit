Replayed cold at `1afc4ab` (macOS arm64, Python 3.12.13, Node 25.6.0). All README steps pass, your mutation suite gives 21 KILLED, and the adapter matches all 43 expected results. One environment finding first, then independent mutations, then your three questions.

**Portability.** `adapter.mjs:110` compares `import.meta.url` with `pathToFileURL(resolve(process.argv[1]))`. Node resolves the first through symlinks and the second not, so on any symlinked path (macOS temp dirs, where `/var` → `/private/var`, or a symlinked checkout) the adapter **does nothing and exits 0**. Reproduced directly: the same copy via `/var/folders/…` → exit 0 with empty stdout; via its real path it runs. Your harness caught it only because the empty stdout fails JSON parsing: `test_research.py` (2 errors, normal and `-O`) and `mutations.py` fail on macOS with the default `TMPDIR` and pass with a non-symlinked one. Suggest `pathToFileURL(realpathSync(process.argv[1]))`, and a non-zero exit if the file is executed but not recognised as the entry point, so this can't recur as a silent success.

**Independent mutations.** Twelve, each forcing one check off, chosen outside your 20-mutation inventory, and compared against the expected `proof_validity` / `anchor_assurance` / `reason` of all 43 vectors (baseline: 0 mismatches):

| check removed | result |
|---|---|
| policy selection (`policy_id`) | caught: `POLICY_NOT_SELECTED` |
| policy authority unknown | caught: `SELF_SUPPLIED_TRUST` |
| policy binding | caught: `POLICY_REF_WRONG`, `POLICY_PROFILE_DIFFERENT` |
| `require_timestamp` honoured | caught: `MISSING_TIMESTAMP` |
| slot "chained" forced true | caught: `UNANCHORED_VALID` |
| unchecked anchor collapsed into `REFUTED` | caught: `CLAIMED_OTS`, so your refutation-vs-absence invariant is held |
| **slot checkpoint commitment** (`s.inclusion.log_root !== e.checkpoint_id`, line 78) | **survives** |
| policy `profile` check (line 35) | survives |
| `anchor_mechanism` allowlist (policy shape) | survives |
| envelope vs policy `anchor_mechanism` match | survives |
| `require_timestamp` boolean type (policy shape) | survives |
| trusted keys taken from the proof instead of policy | not counted: no vector carries keys in a proof, so it never triggered |

The one that matters is line 78. `slot_bridge.py` checks the inclusion against the snapshot the proof itself supplies, so line 78 is the only link from that snapshot to the policy-selected checkpoint, and no vector reaches it. `checkpoint-selection` in your inventory covers line 66, not this one. I'd add a witness (a self-consistent slot proof whose root is not the selected checkpoint → `REFUTED / CHECKPOINT_COMMITMENT_MISMATCH`) and, as defence in depth, also compare the bridge's reported `log_root` with `e.checkpoint_id`. The other four each need one witness; none of them looked redundant with another check.

**Your questions.**

1. *Receipt / RVR boundary.* Agree with it as drawn: a subject record, not a verification receipt, and the envelope is not a seventh RVR field. Reusing `rvr-generic-sha256-equals-v0` for subject-byte identity only is the right scope.
2. *Policy bootstrap.* The authority keys should come from the verifier's own configuration, the embedder declaring them the same way the lens component would declare its sources, never from the envelope. Your `SELF_SUPPLIED_TRUST` vector already holds that line. For public logs, how an authority key is itself published and bound is the real open question. It probably deserves its own short note before a normative profile.
3. *Two Merkle profiles.* Keep the native verifiers separate behind the common envelope, as you have. The line-78 point generalises: for each proof profile, the adapter must bind the native verifier's root to the selected checkpoint, not only check internal consistency.

Thanks for turning this around so quickly. Happy to re-run once the witnesses are in.
