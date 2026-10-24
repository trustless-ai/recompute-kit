# Conformance results

Measured on the isolated candidate; independently authored implementations in one agent session, not external reviewer acceptance.

Base: `b4537d73bda4e4df73c4b105ee516a43c351ba02`. Normal/repeat/-O tests: 13/13 per mode on Windows and WSL Ubuntu. Python and Node each reproduce 52/52 entire expected records. Status population: 14 bounded VERIFIED, 9 REFUTED, 29 UNVERIFIABLE; expected negative results are not authorization grants.

Complete ASCII JSON report, including every canonical UTF-8 hex string, digest, validation stage and native state/reason, is byte-identical across runtimes, modes and OS runs. SHA256 `44960e49f46ad29ec980688168f4da3804eab54dcee9e5801b23ba5219d131bb`.

Canonical main/candidate: 46 PASS / 6 declared NOT RUN / 2 live SKIPPED, exit 0. The complete stdout bytes are identical, SHA256 `1b943bda16f5b84ab4a4070bd8971fcda4c4cf5185ac3c28b4440cf07f505f39`. This is a successful canonical run with explicitly incomplete/live-excluded coverage; the historical DEILS directory remains NOT RUN.

Historical regression: 16 tools/test_*.py scripts passed, plus 3 optimized reruns. Runner tests: failure19, inventory4, checker pins7, unpinned executables6, reporter22, live lifecycle13, runtime19, stale declarations15. Mutation inventory9, empty-corpus15, ungradable expectations14, scan ungradable7. Native collapsed-state, conformance-suite shape and pq controls also passed. Exact commands/stdout/stderr/exit codes are retained.

Historical original DEILS: public six-case corpus plus its evidence/wire controls passed; private original six-archetype self-test passed; unchanged kit stored-hash2/2 and blindhit6/6 passed. This does not establish public /prove deployment behavior.

Pins: all 123 declared digest entries across 30 existing conformance manifests plus this research manifest match (114 pre-existing + 9 new references; duplicate vector references are counted as declarations). External source hashes8/8 match exact Git revisions; Python rfc8785 0.1.4 source hashes match on both OSes. All921 pre-existing Git blobs match byte-for-byte.

No Go/Rust/macOS execution or new GitHub CI job is claimed. Final exact-commit fresh replay is recorded in the external final audit package after local commit.

## Complete corpus

| Case | Expected status | Native state / research reason | Stage | Hash evaluated |
|---|---|---|---|---|
| matching_blinded | VERIFIED | content_bound | commitment | True |
| other_valid_blinding_positive | VERIFIED | content_bound | commitment | True |
| wrong_valid_blinding | REFUTED | content_commitment_mismatch | commitment | True |
| blinding_short | UNVERIFIABLE | blinding_malformed | validation | False |
| blinding_long | UNVERIFIABLE | blinding_malformed | validation | False |
| blinding_uppercase | UNVERIFIABLE | blinding_malformed | validation | False |
| blinding_nonhex | UNVERIFIABLE | blinding_malformed | validation | False |
| blinding_empty | UNVERIFIABLE | blinding_malformed | validation | False |
| blinding_number | UNVERIFIABLE | blinding_malformed | validation | False |
| blinding_boolean | UNVERIFIABLE | blinding_malformed | validation | False |
| blinding_null | UNVERIFIABLE | blinding_malformed | validation | False |
| blinding_array | UNVERIFIABLE | blinding_malformed | validation | False |
| blinding_object | UNVERIFIABLE | blinding_malformed | validation | False |
| blinding_trailing_newline | UNVERIFIABLE | blinding_malformed | validation | False |
| required_blinding_missing | UNVERIFIABLE | RESEARCH_REQUIRED_BLINDING_ABSENT | validation | False |
| blinding_omitted_preimage | REFUTED | content_commitment_mismatch | commitment | True |
| gps_sign_preimage | REFUTED | content_commitment_mismatch | commitment | True |
| latitude_changed | REFUTED | content_commitment_mismatch | commitment | True |
| longitude_changed | REFUTED | content_commitment_mismatch | commitment | True |
| accuracy_changed | REFUTED | content_commitment_mismatch | commitment | True |
| coordinate_substitution | REFUTED | content_commitment_mismatch | commitment | True |
| reuse_other_commitment | VERIFIED | content_bound | commitment | True |
| reordered_members | VERIFIED | content_bound | commitment | True |
| legacy_unblinded | VERIFIED | content_bound | commitment | True |
| withheld | UNVERIFIABLE | content_withheld | disclosure | False |
| legacy_null_withheld | UNVERIFIABLE | content_withheld | disclosure | False |
| unsupported_profile | UNVERIFIABLE | RESEARCH_PROFILE_UNSUPPORTED | admission | False |
| commitment_from_other_field | REFUTED | content_commitment_mismatch | commitment | True |
| latitude_outside | UNVERIFIABLE | RESEARCH_GPS_RANGE_OR_TYPE | validation | False |
| longitude_outside | UNVERIFIABLE | RESEARCH_GPS_RANGE_OR_TYPE | validation | False |
| accuracy_negative | UNVERIFIABLE | RESEARCH_GPS_RANGE_OR_TYPE | validation | False |
| gps_boolean | UNVERIFIABLE | RESEARCH_GPS_RANGE_OR_TYPE | validation | False |
| gps_boundaries | VERIFIED | content_bound | commitment | True |
| accuracy_safe_max | VERIFIED | content_bound | commitment | True |
| safe_min | VERIFIED | content_bound | commitment | True |
| safe_max | VERIFIED | content_bound | commitment | True |
| unsafe_integer | UNVERIFIABLE | RESEARCH_CONTENT_INVALID | admission | False |
| fraction_outside_domain | UNVERIFIABLE | RESEARCH_CONTENT_INVALID | admission | False |
| exponent_outside_domain | UNVERIFIABLE | RESEARCH_CONTENT_INVALID | admission | False |
| malformed_json | UNVERIFIABLE | RESEARCH_CONTENT_INVALID | admission | False |
| duplicate_member | UNVERIFIABLE | RESEARCH_CONTENT_INVALID | admission | False |
| invalid_unicode | UNVERIFIABLE | RESEARCH_CONTENT_INVALID | admission | False |
| nonfinite | UNVERIFIABLE | RESEARCH_CONTENT_INVALID | admission | False |
| negative_zero | VERIFIED | content_bound | commitment | True |
| escaped_unicode | VERIFIED | content_bound | commitment | True |
| utf16_key_order | VERIFIED | content_bound | commitment | True |
| nested_types | VERIFIED | content_bound | commitment | True |
| decomposed_unicode | VERIFIED | content_bound | commitment | True |
| unicode_not_normalized | REFUTED | content_commitment_mismatch | commitment | True |
| privacy_array_not_object | UNVERIFIABLE | RESEARCH_CONTENT_OBJECT_REQUIRED | validation | False |
| ref_bad_prefix | UNVERIFIABLE | malformed_commitment | validation | False |
| malformed_blinding_before_ref | UNVERIFIABLE | blinding_malformed | validation | False |

## Historical failed attempts

The initial environment selected system Python without rfc8785; it was corrected by selecting the isolated interpreter. Initial manifest integration was refused for an undeclared local runner import and absent per-check vector declarations. One environment negative control initially encountered a stale copied vector pin; it was corrected to reread the validly repinned copied manifest. Failed attempts are retained separately; none is counted as a semantic kill. No baseline code was changed to resolve them.
