# DEILS privacy blinding conformance v0

RESEARCH CONFORMANCE CANDIDATE. NOT AN ADOPTED DEILS SPECIFICATION.

This additive experiment tests content binding, format admission and bounded integer/JCS portability. It does not activate DEILS, modify its reveal checker, provide encryption, or establish client integration. Read SPECIFICATION_CANDIDATE.md and SOURCE_AUDIT.md before interpreting any green result. In particular the native missing-blinding error name is NOT ESTABLISHED.

The Python and Node reporters independently compute native evidence. The existing recompute-kit reporter grader compares their complete output with reviewed expectations. Exit 0 from a reporter means only a report was produced. An expected refusal being reproduced is not successful authorization.

## Replay

Python 3.12+ and Node 20+, in an isolated environment:

```sh
python -m pip install rfc8785==0.1.4
P=research/deils-privacy-blinding-conformance-v0
python -B "$P/replay.py"
python -B "$P/test_research.py"
python -B -O "$P/test_research.py"
python -B "$P/mutations.py"
python -B "$P/experiments.py"
python -B "$P/verify_pins.py"
python -B "$P/validate.py" --out /absolute/path/outside/checkout/evidence
```

Keep the selected Python environment first on PATH: the suite declares `python -B verifier.py`. Run the unchanged repository regression workflow in its own fully provisioned environment (Bun, ethers, rfc8785, jsonschema). No new CI job is claimed; the research suite is explicitly invoked via replay.py and not auto-discovered under conformance/. Publication was not authorized.

All fixtures and blinding values are public synthetic test data. A production issuer must use a fresh operating-system CSPRNG 32-byte draw for every commitment. Finite fixtures cannot prove randomness, secrecy or global non-reuse. `fresh_blinding()` and `freshBlinding()` demonstrate 32-byte calls to Python secrets / Node crypto; sampled outputs are not committed and are not entropy proofs.
