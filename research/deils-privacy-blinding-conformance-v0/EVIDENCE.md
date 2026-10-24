# Evidence archive

`evidence-2026-10-24.zip` preserves exact native stdout/stderr (including Windows line endings), invocations, return codes, initial failed attempts, source digest checks and the before/after canonical run. No private source, credentials or client content is present. SHA256 of the ZIP: `caaa352c36ed0655751980f5f158ab3665905e7adb4e9d26245b4239603f7579`.

Windows-final3 and Linux-final2 are current research validation; Linux-final1 contains the complete unchanged historical regression campaign and an earlier research revision. Its research12-test result is historical, superseded by13 tests after the issuer CSPRNG example. Native complete corpus bytes remain the same.

The exact-commit fresh replay, final source patch and publication-free Git receipts are kept in the external final audit package, avoiding a self-referential commit/evidence cycle. Source package inventory is SHA256SUMS.json.

Fresh precommit Windows/Ubuntu copies reproduce13/13 controls normal/repeat/-O,52/52 complete records per runtime,16/16 semantic kills and all non-kill sentinels. Their prehash tests replace the actual SHA256 entry point with a tripwire; malformed blinding never reaches it while the matching control does. Both original and strengthened guard tests are preserved.
