# provenance-anchor.v0 — build-first origination gate

## Purpose

Make the build-first pattern *checkable*, and make **origination** mean what it says. A proposal brought
with a pre-built implementation declares an **origination anchor**; this profile verifies, by recomputation,
that the anchor **committed to that proposal and its implementation artifact** before the proposal opened.

## The claim is declared, so a PASS never overreaches

@zexoverz/Faisal's finding: a free-standing transaction that merely *exists* before a proposal proves
**pre-existence, not origination** — you could move an unrelated pre-existing tx into the record and it would
pass. (The real 8299 anchor commits `sha256("hello")`; it timestamps a demo, it does not bind the WYRIWE
artifact.) The fix is structural: **the record declares its `claim`**, and the verdict carries it.

- `claim: "origination"` — the anchor transaction MUST commit the digest of a canonical **anchor-binding**
  object (below). PASS is `PASS:origination`.
- `claim: "pre_existence"` — only witnessed precedence is required; the anchor need not bind the proposal.
  PASS is `PASS:pre_existence`.

Because PASS is `PASS:<claim>`, pre-existence can never be read as origination. The 8299/8373 anchors are
therefore **`pre_existence` only** — honestly demoted, because they carry no proposal binding.

## anchor-binding.v0 — what an origination anchor must commit

```
{ "schema": "anchor-binding.v0",
  "proposal": { "kind": "erc"|"eip", "id": <int>, "repo": "<canonical repo>" },
  "artifact": { "repo": "<owner/name>", "commit": "<40-hex>" } }
digest = sha256( JCS(object) )
```
The anchor transaction's calldata MUST contain `digest`. The resolver recomputes the digest from the
declared binding and checks the tx commits it (`bound`). The gate additionally requires the binding's
`proposal` to be exactly the scored proposal in its canonical repo (`binding_incoherent` otherwise). If an
`originator` is declared on the anchor, the tx **signer** must equal it (`signer_mismatch` otherwise) —
else the claim stays pre-existence.

## Facts (each independently established)

1. **content identity** — the tx is mined / the commit resolves.
2. **existence witness** — an independent observation of publication time (on-chain: block timestamp; git:
   a separate witness). Never the object's self-reported time.
3. **anchor subject binding** — the anchor's witness references the anchor (git: commit hash in the
   commitment tx calldata).
4. **thread subject binding** — the thread witness is the proposal's opening PR: a `forge_event` in the
   **canonical repository** (erc→ethereum/ERCs, eip→ethereum/EIPs) that **ADDs** the exact-case
   `ERCS/erc-<id>.md`. Enforced in the deterministic gate (canonical repo) and the live resolver
   (added-file + full pagination or fail closed).
5. **anchor → proposal/artifact binding** *(origination only)* — the tx commits the anchor-binding digest,
   the binding is coherent with the scored proposal, and (if declared) the signer is the originator.
6. **witnessed precedence** — the witnessed anchor time strictly precedes the witnessed thread-open time.

The gate fails closed on a non-dict record or non-object resolution, rejects `bool` where an int is required,
and **rejects an empty corpus** (`0 cases` is not a pass). A null `eth_getTransactionByHash` is
`unavailable_rpc`, never `not_found` — a single node's silence cannot prove absence.

## Verdict — closed enumerations

- **PASS** — `PASS:origination` | `PASS:pre_existence`.
- **FAIL** — `malformed_record`, `missing_anchor`, `malformed_anchor`, `missing_thread_open`,
  `malformed_thread_open`, `missing_proposal`, `malformed_proposal`, `malformed_claim`, `malformed_binding`,
  `binding_incoherent`, `anchor_not_found`, `anchor_not_bound`, `signer_mismatch`, `postdates_thread`.
- **UNVERIFIABLE** — `no_publication_witness`, `witness_unresolved`, `witness_not_bound`,
  `incoherent_resolution`, `thread_unwitnessed`, `thread_not_bound`, `anchor_bound_unresolved`,
  `pruned_history`, `rpc_unreachable`, `source_unavailable`.

## Controls — 35 vectors: **5 PASS · 17 FAIL · 13 UNVERIFIABLE**

The headline negative is **`ctrl-8299-tx-in-8373-not-bound`**: the real 8299 transaction (commits
`sha256("hello")`) placed in an *origination* record for erc-8373 → `FAIL:anchor_not_bound`. That is
Faisal's exact attack, now closed: a pre-existing free-standing tx can no longer buy origination. Alongside
it: `binding_incoherent`, `signer_mismatch`, `malformed_binding`, `malformed_claim`,
`anchor_bound_unresolved`, plus the full pre-existence control set (postdates, thread spoof/amendment,
witness binding, canonical repo, fail-closed inputs).

**Real vs model/fixture, stated plainly:**
- **Real:** the on-chain **8299** (`0xc3aeb16d…`) and **8373** (`0x04e1846f…`) anchors resolve live — as
  **`pre_existence`**, because their calldata commits no anchor-binding digest; and PRs **1810/1826/1932**
  resolve to their exact GitHub `created_at`.
- **Model / pending real:** `origination-model-pass` and `origination-signer-pass` are model fixtures — a
  genuine `PASS:origination` requires a real minted anchor whose calldata commits a real
  `anchor-binding.v0` digest (originator = the Vértice gateway signer). That mint is the one act this suite
  is waiting on; until it lands, no row claims a real origination positive.
