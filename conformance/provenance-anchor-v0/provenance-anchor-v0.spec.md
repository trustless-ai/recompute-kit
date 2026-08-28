# provenance-anchor.v0 — build-first origination gate

## Purpose

Make the build-first pattern *checkable*. When a proposal is brought with a pre-built implementation, it
declares an **origination anchor** — the commit, deploy, or on-chain transaction that existed before the
discussion thread opened. This profile verifies that the anchor is present, well-formed, resolvable, and
that its timestamp **strictly precedes** the thread. It is the recompute-don't-trust discipline applied to
provenance at thread-open, so origination never has to be reconstructed later under pressure.

## Scope — what it proves, and what it does not

This profile proves a **witnessed temporal + existence** claim: *this artifact was independently observed
to exist before the thread opened.* It proves nothing about **semantics** — whether the anchored artifact
IS the primitive the spec describes. That is a human judgement (e.g. distinguishing a same-day spec repo
from the implementation it was written from) and is deliberately left to reviewers. A gate that claimed to
settle semantics would be a written rule with no failure mode.

Resolution is split, matching `pq-key-binding.v1/manifest`:
- **`provenance_gate.py`** — the deterministic verdict logic. Resolution is a MODEL INPUT, so the graded
  vector suite is byte-deterministic and CI-runnable.
- **`resolve_anchor.py`** — the live companion that actually fetches the chain / git host and PRODUCES a
  resolution. Feeding its output into the gate closes the loop from declaration to on-chain truth.

## The three-fact contract (per @pipavlo82) — timestamp authority is not uniform

Precedence is decided against an **independent witness**, never a self-reported time. Each anchor is
judged on three separate facts:

1. **content identity** — recompute the object; confirm it exists and its bytes are stable.
2. **existence witness** — establish, from a source the author does NOT control, *when the object was
   publicly observed*.
3. **precedence** — compare that **witnessed** time against thread-open.

The reason the facts must be separate: an on-chain tx/deploy carries its own witness — the block timestamp
is set by consensus. A **bare git commit does not**: author/committer dates are fields inside the commit
object and can be backdated. Recomputing the commit hash proves the bytes and the *claimed* time are
stable, not that the commit existed then. **If no independently-witnessed publication time exists, the
verdict is `UNVERIFIABLE:no_publication_witness`, not PASS** — a self-reported time is not a recomputable
fact.

## Anchor kinds & witness authority

| kind | content identity | existence witness |
|---|---|---|
| `onchain_tx` | tx `0x`+64hex is mined | **intrinsic** — block timestamp (consensus) |
| `onchain_deploy` | deploy tx is mined | **intrinsic** — block timestamp (consensus) |
| `git_commit` | commit `40hex` resolves in `repo` | **separate & required** — a `witness`: `onchain_commitment` of the commit hash, a `transparency_log` entry, or a `forge_event`. A bare commit → UNVERIFIABLE. |

Anchors carry **no self-reported timestamp field** — precedence comes only from the witness.

## Verdict — three states, never a silent green

- **PASS** — content confirmed, an independent witness exists, and the witnessed time strictly precedes
  `thread_opened_ts`.
- **FAIL:`reason`** — a real defect. Closed enumeration:
  - `missing_anchor` — no anchor declared.
  - `malformed_anchor` — anchor (or its witness locator) does not parse.
  - `postdates_thread` — the **witnessed** time is at/after the thread. **The core negative: a
    "build-first" claim whose independent witness is not older than the discussion.**
  - `anchor_not_found` — content resolved to null (a fake reference).
- **UNVERIFIABLE:`reason`** — cannot decide now; MUST NOT pass. Closed enumeration:
  - `no_publication_witness` — content is real but no independent witness of its publication time exists
    (a bare git commit — the case @pipavlo82 flagged). Self-reported time ≠ witness.
  - `witness_unresolved` — a witness is declared but could not be independently resolved now.
  - `pruned_history` — the node pruned the block (real: WYRIWE's May 2026 block is pruned on the public
    Base Sepolia node; an archive node serves it). Why a naive one-RPC check is unsafe.
  - `rpc_unreachable` — RPC down, blocked, or malformed response.
  - `source_unavailable` — git host or commit unreachable.

## Failure modes are proven, not asserted

The vector suite carries five FAIL controls and three UNVERIFIABLE controls alongside the three real
positive anchors, and the can-fail property is shown by mutation: moving a passing anchor's thread earlier
than its origination turns PASS into `FAIL:postdates_thread`. The `pruned_history` state is demonstrated
live — the same real WYRIWE tx returns `pruned` on the public node and `found` on an archive node.

## Controls (the three real anchors + the witness distinction)

| ERC | anchor | witness | thread | verdict |
|---|---|---|---|---|
| 8299 WYRIWE | onchain_tx `0xc3aeb16d…c3319` | block 2026-05-19T22:54:34Z (consensus) | 2026-05-28 | PASS |
| 8373 PQ Binding | onchain_tx `0x04e1846f…c6349c` | block 2026-07-30T18:34:08Z (consensus) | 2026-08-05 | PASS |
| 8309 Mesh Sync | git_commit `…/ccip-router@211c8ba1` | **none (bare commit)** | 2026-06-13 | **UNVERIFIABLE:no_publication_witness** |
| 8309 Mesh Sync (witnessed) | same commit **+ on-chain commitment** | commitment block < thread | 2026-06-13 | PASS |

The bare-commit 8309 row is deliberate: under the three-fact contract, the git anchor that *looked* like a
PASS on a committer date is correctly **UNVERIFIABLE** until an independent witness is supplied. That is the
gate enforcing @pipavlo82's rule against its own author's control, not around it.

## Non-goals

Not a semantic-identity checker; not a contribution-measurement scheme (that is a separate, complementary
surface — a build-first proposal that PASSES this gate can be given weight by a metrics scheme, but the two
are decoupled: this gate answers only "did it exist first?"). Adoption is opt-in per proposal — a change
with no origination claim simply carries no anchor and is out of this gate's scope.
