# ens_write.v0 — ENS Write MCP conformance profile

This profile grades an MCP that builds ENS write transactions. It is **recompute-first**: the
candidate MCP is admissible only if, for each covered operation, the transaction it builds is
**byte-identical** to the one the public ENS rules independently dictate — derivable by anyone,
without trusting the MCP.

## Question in scope

> For each covered ENS write operation, does the candidate build exactly the calldata the public
> rules require?

## Recompute rule (independent derivation)

For each operation, the expected calldata is derived from public rules **alone** — no live chain
read enters the derivation, so it is deterministic and reproducible by any party:

```
calldata = <resolver-fn 4-byte selector> ‖ namehash(name) ‖ abi.encode(remaining args)
```

- `namehash(name)` per **EIP-137 / ENSIP-1** (recursive keccak256 over the dot-separated labels).
- the resolver function ABI (public):

  | tool (candidate)   | function                                    | contract          |
  | ------------------ | ------------------------------------------- | ----------------- |
  | `ens_set_addr`     | `setAddr(bytes32 node, address addr)`       | PublicResolver    |
  | `ens_set_text`     | `setText(bytes32 node, string key, string)` | PublicResolver    |
  | `ens_set_primary`  | `setName(string name)`                      | ReverseRegistrar  |

The reference derivation uses foundry `cast namehash` + `cast calldata <sig> <params…>`; any
implementation of EIP-137 + ABI-encoding reproduces the same bytes.

## Admissibility

For each covered operation, over the inputs pinned in the accompanying vectors:

- **conformant** iff `candidate.calldata == independent.calldata` byte-for-byte;
- **non-conformant** otherwise — a build that constructs a *different* transaction (different
  recipient, node, key/value, or encoding) is caught by the rule, not by any self-comparison.

The suite lists the capability as **Recomputable** iff every covered operation is conformant.

## Vectors

`ens-write-v0.vectors.json` (hash-identified by the suite) pins, per operation, the exact inputs
and the independently-derived `expected` calldata. The vectors are **normative**: an implementation
is conformant iff it reproduces every `expected` from the same inputs — not iff it matches any one
MCP's output.

## Out of scope (v0)

No recompute recipe is defined for, so these are **not covered** (an MCP offering only these is
Attested, not Recomputable):

- `ens_check` — live availability/price (non-deterministic read).
- `ens_register_commit` / `ens_register` — commit/reveal with block-timing dependence.
- `ens_set_contenthash` — CID → ENSIP-7 contenthash byte-encoding (a future recipe).

This profile grades **calldata shape from public rules**; it does not assert which resolver/registry
address a name currently resolves to (a deployment fact, out of scope here).

## References

- EIP-137 (ENS), ENSIP-1 (namehash).
- ENS PublicResolver (`setAddr` / `setText`), ReverseRegistrar (`setName`).
- Receipt export: `receiptos.evidence_capsule.v0`, root by `receiptos-c14n-v0`.
