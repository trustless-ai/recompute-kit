# crc-claim-v0 — cross-reference-console conformance

Gates the `crc/*` recipes (`crc/claim-id` · `crc/lift-v0` · `crc/cell-verify`) through the
**public interface** (`bin/recompute-step` subprocess) — a recipe is never tested against
its own internals.

```bash
python3 conformance/crc-claim-v0/crc_check.py
```

**Vector provenance** (spec + live edge, never this kit's implementation):
trustless-ai/cross-reference-console@`a82f8f1` — `CLAIM.md` (the frozen crc.claim.v0
preimage + pre-hash gate), `CELL-v1.md` (envelopes, triple equality, as_of binding).
Fixtures are the REAL first-edge artifacts:

- `golden-preimage.json` — the `/ledger #236` ClaimPreimage → `sha256:df1a6bfe…` (both
  live lanes reproduced this byte-for-byte before it became a vector here)
- `node1-nostr.cell.json` — Fede's crc.cell.v1 Cell (Nostr event `8530c144…`, BIP-340)
- `node2-eip712.cell.json` — the Vértice gateway attestor's crc.cell.v1 Cell (EIP-712)
- `ledger-236-entry.json` — the entry's `proof_event.content`, for the lift.v0
  byte-compatibility vector (the lift derives the hand-minted claim_id exactly)

**Coverage discipline:** one negative vector at every pre-hash-gate predicate (19 of them —
a rule without a failing vector is a rule nobody has watched fire), tamper + wrong-registered-key
negatives on both envelopes, and the tri-state honored: a missing optional dep (eth-account)
counts SKIPPED/unverifiable, never passed.
