# Conformance vectors

**The canonical authority is the spec + these vectors — not any one implementation.**

`agent-flow.vectors.json` pins, for each step of the composed agent flow, a set of
**public inputs → expected recompute**. An implementation is **conformant iff it
reproduces every `expected` from the same `inputs`** — not iff it matches some reference
SDK's output. That keeps the arbiter language-neutral, which is the whole thesis: *no
trusted implementation in the loop.*

```bash
bin/conformance        # run the reference recompute (via cast) against the vectors
```

## How a language SDK uses this

Every SDK — the TypeScript reference included — CI-gates against the same vectors:

```
for each vector:  sdk.recompute(step, inputs)  ==  vector.expected   ?
```

A TS/Python/Rust/Go port "passes conformance" by reproducing the vectors, exactly like
any other port. The TS reference earns "reference implementation" status by passing them,
not by *being* the spec — a bug in it is a bug, not a redefinition of the protocol.

## Coverage (v0.1)

Pure recomputes — the bytes every SDK must reproduce identically:

| id | step | recompute |
|---|---|---|
| `8004-agent-id` | 8004/agent-id | `keccak256(utf8(agentRef))` |
| `wyriwe-raw` | wyriwe/raw | `keccak256(raw_user_input)` |
| `wyriwe-pipeline` | wyriwe/pipeline | `keccak256(utf8(cid) ‖ raw_input_hash)` |
| `scope-binding` | scope/binding | `keccak256(abi.encode(root, N))` (Guarantee 4) |
| `8301-task-hash` | 8301/task-hash | `keccak256(abi.encode(…7 fields…))` |
| `8275-reputation` | 8275/reputation | `winRate·min(closed,cap)/cap` |

The on-chain **8274 verify** (`WyriweProofVerifier.verify`) is a contract call — identical
for every SDK — so it is not a pure-recompute vector; check it via
`recompute-step 8274/verify`.

## Provenance

Each `expected` was computed authoritatively from its primary source (the ERC text / live
`/ledger`) and is reproduced by `recompute-step`. These vectors and the recompute primitives
live together because the kit *is* the neutral arbiter — see [`../RECOMPUTE.md`](../RECOMPUTE.md).
