# PR86 CLI portability repair — 2026-10-24

Reviewed parent: `7dba06c84e4a5da0dd4a4bfb70785ae9f63c855d`.
Echo review: https://github.com/trustless-ai/recompute-kit/pull/86#issuecomment-6386340001

Independent local reproduction: a real directory symlink returns exit0 with
empty stdout/stderr under the old main guard. The physical path produces all52
results (16672 stdout bytes). Node's loader resolves symlinks while path.resolve
does not. The repair compares realpathSync on both entrypoint identities.
No commitment, admission, validation, fixture or native-result rule changed.

Three new tests cover physical/file-symlink/directory-symlink invocation,
repeat bytes, valid JSON, exact exit status, empty-corpus refusal, import without
CLI side effects, and the canonical runner refusing an exit0 empty report.
The physical removal control restores only the old guard: direct path stays
healthy; linked path returns empty output. That is MISSING_OUTPUT, not KILLED.
Restoration returns all52 results. The test's physical tempfile path is resolved
before constructing real symlinks, including macOS-style symlinked TMPDIR.

Executed Windows and WSL Ubuntu:16/16 research tests normal/repeat/-O;52/52
records in Python/Node;16/16 existing semantic mutations KILLED. Separate six
sentinels remain one each SURVIVED/CRASHED/NO_OP/NOT_APPLIED/MISSING_OUTPUT/
CONTROL_BROKEN, with zero kills. Original vectors and mutation inventory unchanged.
Complete native output SHA256 remains
`37611468426747e1b3d8ce1573514d59e17cfbe59c98582beca4ccfe1816ebe0`.

Linux full campaign:32 commands, all exit0, including16 existing tool scripts
and three optimized reruns. Canonical:46 PASS /6 NOT RUN /2 SKIPPED; complete
stdout SHA256 `1b943bda16f5b84ab4a4070bd8971fcda4c4cf5185ac3c28b4440cf07f505f39`,
unchanged from the original baseline. All123 declared digest references pass.

Windows limitations are not hidden: the first run lacked python3 in PATH.
After provisioning that interpreter alias, canonical and all new tests pass;
two unchanged historical scripts still fail because their fixtures rely on POSIX
shell quoting, sh, or executable shebang scripts (WinError193). The same two
failures were independently reproduced at clean exact main b4537d7. No runner
or historical test was changed to mask these failures. Linux executes both green.
No new local macOS run is claimed; Echo's earlier macOS results remain attributed.

Historical evidence ZIPs, SOURCE_PINS.json, Python reporter and all base files
are preserved. The existing Node checker pin and package inventory are refreshed.
Additive raw evidence archive SHA256: `45ffebc44ae88fd07156a2e216c66ce5d6b444405e5924358ef5cb6e13a9a85a`.
Exact-commit fresh replay and GitHub CI will be recorded at publication, outside
this precommit archive. No new research CI discovery is claimed. This repairs
portability only; the research-only normative and production boundaries remain.
