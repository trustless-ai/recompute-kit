# Source and reuse matrix

Exact commits and file hashes are in SOURCE_PINS.json, checked before research execution. No source license is inferred from GitHub metadata alone.

| Existing component | Direct reuse | Preserved boundary / missing capability |
|---|---|---|
| recompute-kit b9d4fc13 / canonical runner | `run_suite`, declared pins, runtime preconditions, reporter exact-result grader | No new generic engine; all existing files preserved; #78 untouched |
| ERC-8404 RVR 9dd36e88 | Native six-field schema, profile audit/identity, canonical bytes, evidence closure, make_bundle, recompute | Native outcomes and recomputation retained; SHA256_EQUALS proves byte identity only |
| ReceiptOS Verify ac82f93b | Strict parser/canonical bytes, capsule producer/inclusion, local anchor checker | Apache source remains external; local checkpoint key is not public authority |
| invinoveritas ce8c504f | Original slot checker, original 15-vector set | Exact ASCII-hex protocol; original evidence preserved; OTS NOT_COVERED |
| Crystal Receipt pinned vendored interface | Inspected canonicalizer and root-exclusion rules; no copied implementation | Historical top-level anchor exclusion preserved; not the new complete subject-byte hash |
| recompute-kit mcp/receiptos.py | Inspected historical root function; not substituted | Excludes anchor and receipt_root; different domain, not silently equivalent |
| recompute-lens 70b44d85 | API/recipe inspection only | Future recipe/Web Component lives there; no license grant found, no copied source |

The new code is limited to domain admission, policy/binding glue, process bridges, fixtures and tests. Native cryptographic algorithms stay with their original implementations. The RVR canonical contract is reused for verification objects and is not redefined for numeric action payloads.
