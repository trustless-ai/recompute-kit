# id-write.v0 — ENS contenthash write MCP conformance profile

This profile grades an MCP that builds an ENS **`setContenthash`** transaction (point a name at an
IPFS site). It is **recompute-first**: the candidate is admissible only if, for each covered input, the
calldata it builds is **byte-identical** to the one the public rules independently dictate — the
ENSIP-7 contenthash encoding of the CID plus the resolver ABI — derivable by anyone, without trusting
the MCP.

## Question in scope

> For each covered `ipfs://<cid>` target, does the candidate build exactly the `setContenthash`
> calldata the public rules require?

## Recompute rule (independent derivation)

```
calldata = setContenthash selector ‖ namehash(name) ‖ abi.encode(bytes contenthash)
contenthash = 0xe301 ‖ CIDv1( codec, multihash )        # ENSIP-7 / EIP-1577, ipfs-ns
```

- `namehash(name)` per **EIP-137 / ENSIP-1**.
- `contenthash` per **ENSIP-7 / EIP-1577**: the `ipfs-ns` protocol code `0xe3` as an unsigned varint
  (`0xe3 0x01`), followed by the **CIDv1 binary** (`version ‖ codec ‖ multihash`). A CIDv0 (`Qm…`,
  base58btc of a raw sha2-256 multihash) is upgraded to CIDv1 dag-pb (`0x01 0x70 ‖ multihash`); a CIDv1
  (`bafy…`, multibase) is used as-is — so `QmRAQB…` and its CIDv1 form encode to the **same**
  contenthash.
- resolver function ABI (public): `setContenthash(bytes32 node, bytes hash)` on the PublicResolver.

The reference derivation uses foundry `cast namehash` + `cast calldata` and a **second, independent**
ENSIP-7 encoder (`mcp/ens_contenthash.py`) — not the `@ensdomains/content-hash` JS library the candidate
may use — so agreement is a genuine cross-implementation check. That encoder is validated against the
content-hash library's own published golden vectors (CIDv0 + CIDv1 → the same contenthash) and the live
ENS MCP.

## Admissibility

For each covered input, over the vectors pinned in the accompanying file:

- **conformant** iff `candidate.calldata == independent.calldata` byte-for-byte;
- **non-conformant** otherwise — a build that encodes the CID wrong (bad multibase, wrong codec,
  missing the `0xe301` namespace) or targets the wrong node is caught by the rule, not by any
  self-comparison.

The suite lists the capability as **Recomputable** iff every covered input is conformant.

## Vectors

`id-write-v0.vectors.json` (hash-identified by the suite) pins, per input, the exact `{name, contenthash}`
and the independently-derived `expected` calldata. The vectors are **normative**.

## Out of scope (v0)

- **ipns / swarm / onion / arweave** contenthash namespaces — only `ipfs-ns` (`0xe3`) is covered here.
- `ens_check`, `ens_register_commit` / `ens_register` — availability/price + commit-reveal (block-timing
  dependent), Attested (see `ens_write.v0` for the record-setter recipes).

## References

- EIP-137 / ENSIP-1 (namehash), ENSIP-7 / EIP-1577 (contenthash), multiformats CID / multibase /
  multicodec.
- ENS PublicResolver `setContenthash(bytes32,bytes)`.
- Receipt export: `receiptos.evidence_capsule.v0`, root by `receiptos-c14n-v0`.
