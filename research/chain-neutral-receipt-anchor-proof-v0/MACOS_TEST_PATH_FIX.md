# macOS temporary-path test correction

This is a one-line test portability correction following Echo's independent
[cc8e38b replay](https://github.com/trustless-ai/recompute-kit/pull/85#issuecomment-6364685624).
It does not change the adapter, native verifiers, vectors, mutation inventory,
ERC-8404 Core, source pins, runner or workflow.

`test_symlink_entrypoint_and_removal` now resolves the temporary root before
constructing its physical positive-control path. The deliberately linked path
is still a real symlink. On macOS `/tmp` can itself be a symlink; previously the
supposed physical control was lexical too, causing the intentionally reverted
adapter to no-op there and the test to error on empty JSON.

## Executed evidence

- Reproduced the exact old JSONDecodeError on WSL using a symlinked TMPDIR.
- The corrected single test passes normal/repeat/`-O` under that same setup.
  The external probe records resolved physical paths and actual linked parents.
- Complete research replay: 18 tests per mode, 49 vectors, 26 targeted corpus
  mutations KILLED, no target survivors/crashes/uncovered cases; restoration and
  positive controls preserved. Existing diagnostic non-kills remain excluded.
- Windows and actual WSL full normal/repeat/`-O` machine outputs match cc8e38b
  byte-for-byte per platform. Unittest timing is not claimed deterministic.
- Historical regressions: 105 runner tests; 9 inventory, 15 nonempty,
  14 ungradable and 7 scan tests each normal/`-O`.
- Canonical output unchanged: 46 PASS / 6 NOT RUN / 2 SKIPPED. 137 declared pins
  recomputed successfully; external source pins and all prior evidence preserved.

The original 26-mutation distinction remains: 25 verdict witnesses and one
early native-evidence witness. No new semantic kill is attributed to this test
path correction. The reproduced old test error is not counted as a mutant kill.

## Replay

With README dependencies and `CHAIN_PROOF_SOURCES` configured:

```sh
P=research/chain-neutral-receipt-anchor-proof-v0
python3 -B "$P/test_research.py" ResearchTests.test_symlink_entrypoint_and_removal
python3 -B -O "$P/test_research.py" ResearchTests.test_symlink_entrypoint_and_removal
python3 -B "$P/validate.py" --historical --out /absolute/outside-checkout/evidence
```

For the independent macOS replay, use the default TMPDIR without overriding it.
The external Linux probe is in `evidence/macos-test-fix/symlink_probe.py` and
requires TMPDIR to point through a real symlink. Its `old` mode expects the
original error; its `fixed` mode requires success plus both physical/link checks.

Exact commands, outputs/digests and pre-commit results:
`evidence/macos-test-fix/summary.json` and adjacent focused raw logs.
Full logs are retained in the author evidence archive; CI uploads fresh raw
research logs. Fresh exact-commit replay and new-head CI are post-commit gates
and will be reported in the publication comment, not presumed here.

This is not a local macOS execution claim. Echo's semantic replay is independent
reviewer evidence; the final macOS default-TMPDIR test needs their repeat.
The PR stays Draft. No normative, public-authority, OTS or execution claim changes.
