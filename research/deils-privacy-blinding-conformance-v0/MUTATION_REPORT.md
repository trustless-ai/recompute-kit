# Physical mutation report

Sixteen physical mutations: eight boundaries x two independent runtimes. All16 KILLED; zero SURVIVED/CRASHED/NO_OP/NOT_APPLIED/MISSING_OUTPUT/CONTROL_BROKEN in the semantic campaign.

Every mutation matches exactly once, runs in a newly created directory containing only that source file, and is executed in a new process. Python uses -B and PYTHONDONTWRITEBYTECODE=1; the disposable directory contains no existing .pyc. No stale bytecode can supply the mutated main script. Source bytes in the real checkout are never modified and are compared afterward.

A kill requires process exit0 with a complete parseable reporter output, healthy named controls, and a differing exact asserted native result for the designated witness. Thus an admission-to-mismatch reclassification can be a real semantic kill even without false VERIFIED. Crashes, timeouts, malformed/missing reports and broken controls are never kills. Pins are deliberately outside this source-perturbation experiment; no stale-pin failure is used as a kill.

For preimage omission the unaffected positive is legacy_unblinded, with withholding as an additional control; privacy positives necessarily exercise the mutated preimage and are not misrepresented as preserved. All other named positives are documented below.

| Mutation | Witness | Healthy controls | Outcome |
|---|---|---|---|
| skip-format/python | blinding_nonhex | matching_blinded, other_valid_blinding_positive, legacy_unblinded | KILLED |
| skip-format/node | blinding_nonhex | matching_blinded, other_valid_blinding_positive, legacy_unblinded | KILLED |
| uppercase/python | blinding_uppercase | matching_blinded, other_valid_blinding_positive, legacy_unblinded | KILLED |
| uppercase/node | blinding_uppercase | matching_blinded, other_valid_blinding_positive, legacy_unblinded | KILLED |
| wrong-length/python | blinding_short | matching_blinded, other_valid_blinding_positive, legacy_unblinded | KILLED |
| wrong-length/node | blinding_short | matching_blinded, other_valid_blinding_positive, legacy_unblinded | KILLED |
| malformed-as-mismatch/python | blinding_nonhex | matching_blinded, other_valid_blinding_positive, legacy_unblinded | KILLED |
| malformed-as-mismatch/node | blinding_nonhex | matching_blinded, other_valid_blinding_positive, legacy_unblinded | KILLED |
| omit-blinding/python | blinding_omitted_preimage | legacy_unblinded, withheld | KILLED |
| omit-blinding/node | blinding_omitted_preimage | legacy_unblinded, withheld | KILLED |
| skip-required/python | required_blinding_missing | matching_blinded, other_valid_blinding_positive, legacy_unblinded | KILLED |
| skip-required/node | required_blinding_missing | matching_blinded, other_valid_blinding_positive, legacy_unblinded | KILLED |
| gps-sign/python | gps_sign_preimage | matching_blinded, other_valid_blinding_positive, legacy_unblinded | KILLED |
| gps-sign/node | gps_sign_preimage | matching_blinded, other_valid_blinding_positive, legacy_unblinded | KILLED |
| skip-comparison/python | wrong_valid_blinding | matching_blinded, other_valid_blinding_positive, legacy_unblinded | KILLED |
| skip-comparison/node | wrong_valid_blinding | matching_blinded, other_valid_blinding_positive, legacy_unblinded | KILLED |

Separate physical harness sentinels: one expected SURVIVED, one CRASHED, one NO_OP, one NOT_APPLIED, one MISSING_OUTPUT, one CONTROL_BROKEN; zero kills. These are deliberate classifier tests, not six extra semantic mutants. A timeout classification control is also non-kill. Exact original/mutated expressions, source hashes, differing cases, native stdout/stderr and return codes appear in raw mutations.stdout and mutation-sentinels.stdout.

This is finite guard evidence, not full mutation coverage or independent acceptance.
