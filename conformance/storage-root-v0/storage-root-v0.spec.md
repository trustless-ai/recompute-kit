# storage-root.v0 — 0G Storage root MCP conformance profile

This profile grades an MCP that returns the **0G Storage content root** for a blob (e.g. `og_root`,
or the `rootHash` an `og_store` path computes). It is **recompute-first**: the candidate is admissible
only if, for each covered input, the root it reports is **byte-identical** to the one the public 0G
flow-merkle rules independently dictate — derivable by anyone from the bytes alone, without trusting
the MCP and without performing any upload.

## Question in scope

> For each covered blob, does the candidate report exactly the 0G Storage rootHash the public
> flow-merkle rules require?

## Recompute rule (independent derivation)

The rootHash is a pure function of the content bytes — no network, no chain read, no signer:

```
chunks       = ceil(len(content) / 256)                       # 256-byte sectors
paddedChunks = flow-pad(chunks)                               # round up (see below)
data         = content ‖ 0x00 * (paddedChunks*256 - len)     # zero-pad to whole chunks
leaf_i       = keccak256(data[i*256 : (i+1)*256])            # one leaf per 256-byte chunk
segmentRoot  = flow_merkle(leaves within each 256 KiB segment)
rootHash     = flow_merkle(segment roots)
```

- **chunk size** = 256 bytes; **segment** = 1024 chunks (256 KiB).
- **flow-pad**: `nextPow2(chunks)`; if already a power of two, no pad; else round `chunks` up to a
  multiple of `max(1, nextPow2(chunks)/16)`.
- **flow_merkle** (the 0G tree): pair leaves bottom-up left-to-right, `parent = keccak256(left ‖ right)`;
  an odd node at any level is **carried** to the next level unchanged (it is *not* duplicated and the
  tree is *not* padded to a power of two). A single leaf is its own root.

Reference: 0G protocol `0gfoundation/0g-ts-sdk` (`MerkleTree.build`, `AbstractFile.segmentRoot`,
`constant.ts`, `utils.ts`). Any faithful reimplementation reproduces the same bytes; the recompute-kit
carries a **second, independent** implementation in Python (`mcp/zerog_merkle.py`) so the check is a
genuine cross-implementation agreement, not the SDK compared against itself.

## Admissibility

For each covered input, over the blobs pinned in the accompanying vectors:

- **conformant** iff `candidate.rootHash == independent.rootHash` byte-for-byte;
- **non-conformant** otherwise — an MCP that reports a different root (wrong padding, wrong chunking,
  wrong combination) is caught by the rule, not by any self-comparison.

The suite lists the capability as **Recomputable** iff every covered input is conformant.

## Vectors

`storage-root-v0.vectors.json` (hash-identified by the suite) pins, per input, the exact content and
the independently-derived `expected` rootHash. The `expected` values were produced by the Python
reference and cross-checked against (a) the 0G SDK's own published unit-test golden roots and (b) a
live 0G MCP `og_store` on the same bytes. The vectors are **normative**: an implementation is
conformant iff it reproduces every `expected` from the same content.

## Out of scope (v0)

- `og_store_artifact` — performs a **live upload** (gas + network side-effect); it is an *action*, not
  a pure derivation, so it lists **Attested**. Its returned `rootHash`, however, must equal this
  profile's root for the same content, and can be checked with `og_root` offline.
- `og_fetch_artifact` — a content-addressed read; verify-only (fetched bytes must hash back to the
  requested root). Not a build, so Attested.
- Availability/redundancy/proof-of-storage on the 0G network — a deployment fact, out of scope here.

## References

- 0G Storage flow-merkle (`0gfoundation/0g-ts-sdk`): `constant.ts`, `file/MerkleTree.ts`,
  `file/AbstractFile.ts`, `file/utils.ts`.
- Receipt export: `receiptos.evidence_capsule.v0`, root by `receiptos-c14n-v0`.
