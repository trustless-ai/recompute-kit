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
| `receiptos-c14n-v0` | receiptos/canonicalize | `0x·sha256(C(strip_anchor(E)))` — profile receiptos-c14n-v0 (JCS + anchor-strip), RAILS/ReceiptOS §2.8; the π case exercises literal-UTF-8 |

The on-chain **8274 verify** (`WyriweProofVerifier.verify`) is a contract call — identical
for every SDK — so it is not a pure-recompute vector; check it via
`recompute-step 8274/verify`.

## Cross-repo conformance

A vector can also be cross-verified by **independent implementations living in other repos**.
The kit records the pointer so the citation goes both ways (recompute-native, no drift).

| vector | independent reproductions | record |
|---|---|---|
| `receiptos/receipt-hash` — receipt chain-hash `sha256(decision ‖ prev)` | **three independently-authored implementations** — recompute-kit · ReceiptOS reference · a from-spec rebuild (`@babyblueviper1`, never read the other two) — byte-exact on both real evidence capsules and all negative fixtures. (The reference's browser + script paths are *surfaces* of one implementation, not separate authors — hence three, not four.) | crystal-receipt [`docs/CONFORMANCE_INDEX.md`](https://github.com/pipavlo82/crystal-receipt/blob/main/docs/CONFORMANCE_INDEX.md) → row `pre-post-gate-composed` |
| `chronicle_checkpoint_continuity.v0` — pairwise checkpoint continuity (final 20 normative vectors; full adjacent precedence chain shape→local-verify→ref→sequence) | **two independently-authored implementations** — Pavlo's reference (crystal-receipt) · a from-spec rebuild (`TMerlini`, never read `crystal-receipt/src/**`), incl. the root canonicalization reverse-engineered from golden roots — 20/20 agree with pinned `expected`, 22/22 golden roots. | [`chronicle-checkpoint-continuity-v0/`](./chronicle-checkpoint-continuity-v0/) · spec+vectors hash-pinned from crystal-receipt @ `13187b29` (vectors SHA-256 `c369bd39…`) |

Related seam artifact — the **eligibility ↔ verdict** correspondence (the kit's tri-state exits
`0/1/2` ↔ the gate's `admit/reject/undetermined` ↔ ReceiptOS binary admissibility) is pinned in a
three-way co-signed note: [gist `TMerlini/0f5f426e…`](https://gist.github.com/TMerlini/0f5f426e400197a670874f17c4451c99),
which pairs with crystal-receipt `fixtures/invalid/EXPECTED.md@29f36fb`. Exit numbers are
implementation-specific; the **verdict vocabulary** is what's normative.

## Provenance

Each `expected` was computed authoritatively from its primary source (the ERC text / live
`/ledger`) and is reproduced by `recompute-step`. These vectors and the recompute primitives
live together because the kit *is* the neutral arbiter — see [`../RECOMPUTE.md`](../RECOMPUTE.md).
