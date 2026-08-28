# provenance-anchor.v0 — build-first origination gate

## Purpose

Make the build-first pattern *checkable*. When a proposal is brought with a pre-built implementation, it
declares an **origination anchor** — the commit or on-chain transaction that existed before the discussion
opened — and this profile verifies, by recomputation, that the anchor was **independently witnessed** to
exist before the proposal opened. Recompute-don't-trust, applied to provenance at thread-open.

## Scope — what it proves, and what it does not

It proves a **witnessed temporal + existence** claim: *this artifact was independently observed to exist
before the proposal opened.* It proves nothing about **semantics** — whether the anchored artifact IS the
primitive the spec describes (human review; e.g. distinguishing a same-day spec repo from the
implementation it was written from). A gate claiming to settle semantics would be a written rule with no
failure mode.

Resolution is split, matching `pq-key-binding.v1/manifest`:
- **`provenance_gate.py`** — deterministic verdict logic. Resolution is a MODEL INPUT, so the graded suite
  is byte-deterministic.
- **`resolve_anchor.py`** — the live companion that fetches AND enforces the facts (subject binding on both
  sides, no self-reported time, witnessed + added thread-open), producing the resolution the gate consumes.

## Five facts, each independently established

Precedence is decided between two **witnessed** times, and every witness must be **bound** to the thing it
witnesses:

1. **content identity** — recompute the object; confirm it exists and its bytes/hash are stable.
2. **existence witness** — an observation of publication time from a source the author does **not**
   control. Never the object's own self-reported time.
3. **anchor subject binding** — the anchor witness must reference *this* anchor. An on-chain commitment of a
   commit must carry that commit hash in its calldata; the block timestamp of an unrelated transaction is
   not a witness of the commit.
4. **thread subject binding** — the thread witness must be *this proposal's* **opening** boundary. A
   `forge_event` PR binds only if it **ADDs** the proposal's spec file (`ERCS/erc-<id>.md`,
   `status == "added"`) — a later amendment that merely *modifies* the file does not bind, so a caller
   cannot substitute a later PR to manufacture a later thread-open. All PR-file pages are read, or the
   resolver fails closed.
5. **witnessed precedence** — the witnessed anchor time strictly precedes the witnessed **thread-open**
   time; both sides are witnessed facts, never unverified record fields.

The gate also refuses to trust the resolution blindly: it checks the resolution is **coherent** with the
declared anchor (a bare commit cannot claim a witness → `incoherent_resolution`), **fails closed** on a
non-dict record or non-object resolution, and **rejects `bool`** where an integer is required.

## Record & anchor kinds

The record carries `proposal {kind, id}` (the scored subject — `erc` or `eip`), `thread_open.witness`, and
`anchor`.

| anchor kind | content identity | existence witness | subject binding |
|---|---|---|---|
| `onchain_tx` | tx (`0x`+64hex) is mined | **intrinsic** — block timestamp (consensus) | the tx is its own subject |
| `git_commit` | commit (`40hex`) resolves in `repo` | **separate & required** — a `witness`: `onchain_commitment` \| `transparency_log` \| `forge_event`. Bare commit → UNVERIFIABLE. | `onchain_commitment` MUST carry the commit hash in calldata; unwired `transparency_log`/`forge_event` → `witness_unresolved` |

`onchain_deploy` is **not** in v0 (was declared-but-unexecutable; removed rather than shipped broken).
Anchors carry **no self-reported timestamp field**. Thread-open `witness` is `forge_event` (resolves the
ERC PR's GitHub-stamped `created_at`, bound via the added-file rule above) or `onchain_commitment`.

## Verdict — three states, closed enumerations, never a silent green

- **PASS** — content confirmed, both witnesses present & bound, thread-open witnessed & added, witnessed
  anchor time strictly before witnessed thread-open time.
- **FAIL** — `malformed_record`, `missing_anchor`, `malformed_anchor`, `missing_thread_open`,
  `malformed_thread_open`, `missing_proposal`, `malformed_proposal`, `anchor_not_found`, `postdates_thread`.
- **UNVERIFIABLE** — `no_publication_witness`, `witness_unresolved`, `witness_not_bound`,
  `incoherent_resolution`, `thread_unwitnessed`, `thread_not_bound`, `pruned_history`, `rpc_unreachable`,
  `source_unavailable`.

## Controls — 26 vectors: **3 PASS · 12 FAIL · 11 UNVERIFIABLE**

Each defect class has a control that must not pass, including `thread_not_bound` (unrelated PR **and** a
real amendment PR that only modifies the file — `ethereum/ERCs` #1933 modifies `erc-7730.md`), `malformed_
record`, `missing`/`malformed_proposal`, `bool chain_id`, and non-object resolution. Can-fail is shown by
mutation (move the witnessed thread-open before the witnessed anchor → `FAIL:postdates_thread`).

**Real vs synthetic / fixture, stated plainly:**
- **Real:** every row referencing `ethereum/ERCs` PRs **1810 / 1826 / 1932** carries that PR's **exact**
  GitHub `created_at` (`1781183206` / `1781874038` / `1786012951`), each PR resolving live to that time and
  binding to its proposal by the added-file rule; and only the on-chain **8299** (`0xc3aeb16d…`) and
  **8373** (`0x04e1846f…`) anchors resolve live.
- **Synthetic:** postdates ordering controls use proposal id `>= 90000` and PR `>= 990000` with fabricated
  times — *not* presented as real PRs. The witnessed-**8309** PASS and all *witness* `tx` values
  (`0x0000…`/`0x1111…`/`0x3333…`) are opaque model fixtures; the bare-commit 8309 is correctly
  `UNVERIFIABLE:no_publication_witness` until a real on-chain commitment exists.
