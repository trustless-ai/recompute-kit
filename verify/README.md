# recompute-kit-verify

**Recompute a recompute-kit receipt on your own machine. Trust no one — not even us.**

Every recompute-kit / MCP receipt is a `recompute-kit.conformance_proof_object.v0` (it embeds a
`receiptos.evidence_capsule.v0`). This package re-derives the receipt's `receipt_root` locally and reads the
capsule's own conformance verdict *verbatim* — so a receipt is only trusted once **you** recomputed it.

**Stdlib only. No network. No dependency on us.**

## Install

```sh
pip install recompute-kit-verify
```

## Use

```sh
recompute-verify receipt.json        # exit 0 = verified-good, 1 = verified-bad, 2 = UNVERIFIABLE
cat receipt.json | recompute-verify -
```

```python
from recompute_kit_verify import verify_object
import json
verify_object(json.load(open("receipt.json")))
# {"status": "verified-good", "root": "0x…", "verifier_result": {"ok": true, "status": "verified"}, ...}
```

## The tri-state (couldn't-check is its own verdict, never a silent pass)

| status | meaning |
| --- | --- |
| `verified-good` | the root recomputes **and** the carried conformance verdict is ok |
| `verified-bad` | the root mismatches (tampered / mis-derived) **or** the carried verdict is rejected |
| `UNVERIFIABLE` | not parseable, no capsule to recompute, or no stored root / verdict to check |

## What it checks

- **Integrity** — `receipt_root == "0x" + sha256(JCS(receipt \ {anchor, receipt_root}))` (`receiptos-c14n-v0`),
  recomputed here, compared to the stored root. A one-field tamper breaks it.
- **Verdict** — the capsule's own `verifier_result` (`{ok, status}`), carried verbatim; the verdict is never
  inferred from the root match.
- **Signature** — a lane reserved for signed receipts; today receipts are integrity-bound by `receipt_root`.

Recompute the source: <https://github.com/trustless-ai/recompute-kit> · `mcp/receiptos.py`.
