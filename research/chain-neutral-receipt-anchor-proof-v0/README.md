# Chain-neutral action subject and optional anchor proof v0

**SPECIFICATION CANDIDATE — NOT NORMATIVE — NOT PRODUCTION-READY — AWAITING INDEPENDENT REVIEW.**

This isolated research directory proposes an action **subject record**, plus a separately selected optional inclusion envelope. It is not a replacement verification receipt. ERC-8404 already supplies the six-field verification receipt, two native status axes, canonical JSON and content-addressed Verification Profile. Read [ERC8404_RECEIPT_BOUNDARY.md](ERC8404_RECEIPT_BOUNDARY.md) first.

The executable adapter composes unchanged, exact-pinned ReceiptOS and invinoveritas source implementations. It does not implement a new Merkle verifier, generic verification engine, executor, judgment procedure or timestamp verifier. Independently authenticated caller policy selects the log, profile, checkpoint and authority. All bundled keys and examples are public synthetic laboratory fixtures.

Read [SPECIFICATION_CANDIDATE.md](SPECIFICATION_CANDIDATE.md), [TRUST_POLICY.md](TRUST_POLICY.md), [PROOF_PROFILES.md](PROOF_PROFILES.md), and [LIMITATIONS.md](LIMITATIONS.md). Measured results and failed attempts are recorded in [CONFORMANCE_RESULTS.md](CONFORMANCE_RESULTS.md) and `evidence/`. Frozen upstream artifacts are never rewritten.

The same-PR self-review corrections are documented in [REVIEW_CORRECTIONS.md](REVIEW_CORRECTIONS.md): log-identity type admission, separately witnessed policy bindings, and an asserted RVR scalar-order boundary. Original evidence remains preserved as history; current counts are reported separately.

The later [Echo review repairs](ECHO_REVIEW_REPAIRS.md) add linked-path CLI admission, an independent native slot-checkpoint check and six policy/checkpoint witnesses. Current corpus: 49 cases; mutation inventory: 26, with the early native-evidence assertion distinguished from a verdict bypass. Original 43 vectors and prior captured evidence are retained unchanged.

## Replay

Python 3.12+, Node 20+, Git, and Python `rfc8785` for the independent cross-runtime test. The adapters and native RVR/slot bridges otherwise use standard libraries. From the repository root, with an isolated Python environment activated:

```sh
export PYTHONDONTWRITEBYTECODE=1
export CHAIN_PROOF_SOURCES=/absolute/path/outside/repository/chain-proof-sources
export CHAIN_PYTHON=python3
python3 -m pip install rfc8785==0.1.4
P=research/chain-neutral-receipt-anchor-proof-v0
python3 -B "$P/bootstrap.py" "$CHAIN_PROOF_SOURCES"
python3 -B "$P/replay.py"
python3 -B "$P/test_research.py"
python3 -B -O "$P/test_research.py"
python3 -B "$P/rvr_boundary.py"
python3 -B "$P/mutations.py"
node "$P/adapter.mjs" --native < "$P/vectors.json"
python3 -B tools/run_conformance.py
```

The final command is the historical repository suite and additionally requires the runtimes/packages in the unchanged repository setup instructions. `validate.py --out /absolute/evidence/path` captures the complete research replay; add `--historical` only in that fully provisioned environment. Output paths must stay outside the checkout for clean exact-commit replay. `SHA256SUMS.json` inventories this research package; `evidence/` preserves raw captured bytes, including diagnostic Windows line endings, through scoped Git attributes.

`replay.py` calls the existing canonical runner's `run_suite` and reporter grader unchanged. This research suite is **not** auto-discovered under `conformance/*`; its additive dedicated CI workflow executes the declared suite and all research controls. The shared conformance workflow remains byte-identical. A green negative vector means its expected refusal was reproduced, not that its supplied proof was valid.

The original invinoveritas vectors are external, unchanged sources. Replay them with `python3 -B "$CHAIN_PROOF_SOURCES/invino/examples/decision-receipt/slot_log_check.py" --vectors "$CHAIN_PROOF_SOURCES/invino/examples/decision-receipt/slot_log_vectors.json"`. Independent OpenTimestamps authentication is **not established**.
