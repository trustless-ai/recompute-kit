# provenance-anchor.v0 — build-first origination gate

## Purpose

Make the build-first pattern *checkable*. When a proposal is brought with a pre-built implementation, it
declares an **origination anchor** — the commit or on-chain transaction that existed before the discussion
opened — and this profile verifies, by recomputation, that the anchor was **independently witnessed** to
exist before the thread. Recompute-don't-trust, applied to provenance at thread-open.

## Scope — what it proves, and what it does not

It proves a **witnessed temporal + existence** claim: *this artifact was independently observed to exist
before the thread opened.* It proves nothing about **semantics** — whether the anchored artifact IS the
primitive the spec describes (human review; e.g. distinguishing a same-day spec repo from the
implementation it was written from). A gate that claimed to settle semantics would be a written rule with
no failure mode.

Resolution is split, matching `pq-key-binding.v1/manifest`:
- **`provenance_gate.py`** — deterministic verdict logic. Resolution is a MODEL INPUT, so the graded suite
  is byte-deterministic.
- **`resolve_anchor.py`** — the live companion that fetches AND enforces the facts (subject binding, no
  self-reported time, witnessed thread-open), producing the resolution the gate consumes.

## Four facts, each independently established

Precedence is decided between two **witnessed** times, and every witness must be **bound** to the thing it
witnesses:

1. **content identity** — recompute the object; confirm it exists and its bytes/hash are stable.
2. **existence witness** — an observation of publication time from a source the author does **not**
   control. Never the object's own self-reported time.
3. **subject binding** — the witness must reference *this* subject. An on-chain commitment of a commit must
   actually carry that commit hash in its calldata; the block timestamp of an unrelated transaction is not
   a witness of the commit.
4. **witnessed precedence** — the witnessed anchor time strictly precedes the witnessed **thread-open**
   time, where thread-open is itself a witnessed fact (the ERC PR's forge-stamped creation), never an
   unverified record field a caller can move later.

The gate additionally refuses to trust the resolution blindly: it checks the resolution is **coherent**
with the declared anchor (a bare commit cannot claim a witness → `incoherent_resolution`), **fails closed**
on a non-object resolution, and **rejects `bool`** where an integer is required.

## Anchor kinds & witness authority

| kind | content identity | existence witness | subject binding |
|---|---|---|---|
| `onchain_tx` | tx (`0x`+64hex) is mined | **intrinsic** — block timestamp (consensus) | the tx is its own subject |
| `git_commit` | commit (`40hex`) resolves in `repo` | **separate & required** — a `witness`: `onchain_commitment` \| `transparency_log` \| `forge_event`. Bare commit → UNVERIFIABLE. | `onchain_commitment` MUST carry the commit hash in calldata; unwired `transparency_log`/`forge_event` → `witness_unresolved` |

`onchain_deploy` is **not** in v0 (it was declared-but-unexecutable — a KeyError on a missing creation tx;
removed rather than shipped broken). Add it back only with a real creation-tx resolution. Anchors carry
**no self-reported timestamp field** — precedence comes only from witnesses.

Thread-open is a `thread_open.witness` of kind `forge_event` (resolves the ERC PR's GitHub-stamped
`created_at`) or `onchain_commitment`. It is the *proposal-opening* boundary; if an earlier witnessed
discussion event exists, use that. Unwitnessed thread-open → `thread_unwitnessed`, never PASS.

## Verdict — three states, closed enumerations, never a silent green

- **PASS** — content confirmed, witness present & bound, thread-open witnessed, witnessed anchor time
  strictly before witnessed thread-open time.
- **FAIL** — `missing_anchor`, `malformed_anchor`, `missing_thread_open`, `malformed_thread_open`,
  `anchor_not_found`, `postdates_thread`.
- **UNVERIFIABLE** — `no_publication_witness`, `witness_unresolved`, `witness_not_bound`,
  `incoherent_resolution`, `thread_unwitnessed`, `pruned_history`, `rpc_unreachable`, `source_unavailable`.

## Controls — 21 vectors: **3 PASS · 9 FAIL · 9 UNVERIFIABLE**

Each defect class has a control that must not pass: postdates (anchor and witness variants), malformed
(anchor / witness locator / thread-open / bool chain_id), missing (anchor / thread-open), fake anchor,
bare-commit-no-witness, incoherent resolution, unbound witness, unresolved transparency backend,
unwitnessed thread, non-object resolution, and the three content-unavailability states. Can-fail is shown
by mutation (move the witnessed thread-open before the witnessed anchor → `FAIL:postdates_thread`).

**Real vs fixture, stated plainly:** only the on-chain **8299** (`0xc3aeb16d…`) and **8373**
(`0x04e1846f…`) anchors resolve live to the timestamps carried here, and the thread-open PR numbers
(1810 / 1826 / 1932) are real `ethereum/ERCs` PRs whose `created_at` resolves live. The witnessed-**8309**
PASS row and every *witness* `tx` value (`0x0000…`, `0x1111…`, `0x2222…`, `0x3333…`) are **opaque model
fixtures** — no on-chain commitment for the ccip-router commit exists yet; the bare-commit 8309 is
correctly `UNVERIFIABLE:no_publication_witness` until one does. That row is the gate enforcing the witness
rule against its own author's control, not around it.
