# pq_key_binding.v1 — cutoff enforcement

v1 cutoff enforcement for ERC-8373. A faithful port of the live gateway enforcer
(`vertice-gateway/src/lib/pqCutoff.ts`, the operative side of the profile). Two changes over
[pq-key-binding-v0](../pq-key-binding-v0/), both to stop the back catalogue being retroactively
invalidated:

1. **Baseline activation.** The baseline binding (earliest, key_epoch 0) governs from time **0**, not
   from its anchor time. Anchoring gives a binding a provable time, not a birthday — an artifact
   anchored *before* the baseline's own registration is still governed by it, and admits classical-only
   pre-cutoff. Successors keep `activated_at = their anchor time`, so a rotation still cannot claim
   retroactive coverage. This turns v0's `no_in_force_binding → REJECT` for a pre-baseline artifact
   (which retro-invalidated the oldest back catalogue) into `anchored_before_cutoff → ADMIT`.

2. **Tri-state evidence.** The verdict carries `evidence ∈ {verified, refuted, unverifiable}`; the
   boolean `decision` (ADMIT/REJECT) is a *derived projection*. "checked and failed" (refuted) and
   "never checked" (unverifiable) no longer collapse into one REJECT; `unverifiable` carries a reason.

## The distinction v0 hid

v0's single `no_in_force_binding` reason covered two cases that deserve opposite answers:

| case | anchored | governing binding | v0 | **v1** |
|---|---|---|---|---|
| **pre-baseline** — before the first binding registered | before cutoff | none yet | REJECT | **ADMIT** (`anchored_before_cutoff`) |
| **post-revocation** — after a binding's authority ended | before cutoff | none (revoked) | REJECT | **REJECT** (`no_in_force_binding`) |

A pre-baseline artifact is innocent back catalogue → admit. A post-revocation artifact is governed by
a deliberate trust-ending signal → reject, **even pre-cutoff**, because a revocation is stronger than
the consumer's cutoff. v1 admits the first and keeps rejecting the second.

## ⚠ Held for review — @pipavlo82

The post-revocation half is the revocation lane. This PR encodes *post-revocation artifact → REFUTED /
`no_in_force_binding` even when pre-cutoff* (a revocation overrides the back-catalogue admit), matching
the live enforcer. **Not for merge until that semantics is signed off** as the intended rule rather
than an implementation artefact.

## Before this (and the ERC assets) land
- Cross-check the live TS enforcer (`pqCutoff.ts` `runSuite`) against these v1 vectors — the "two
  independent implementations converge" claim.
- Then promote `assets/erc-8373/` (ethereum/ERCs #1932) from v0 to v1 cutoff assets + add the Related
  Work paragraph (Lean Consensus PQ registry: expiry-from-statefulness vs explicit anchored
  authority-termination).

## Manifest-chain `governs_from` resolution (spec §10.2.1)

`manifest_resolve.py` is the chain-completeness half of `governs_from`: the earliest manifest that
governs a binding is **proven** by reconstructing the manifest chain from genesis (`prev_manifest_cc =
null`), never taken from the earliest *visible* manifest. It recomputes each manifest's content address
and enforces the two fail-closed rules the spec states normatively — a required prev link that cannot
be fetched and recomputed makes `governs_from` `UNRESOLVED`/`UNVERIFIABLE` (never earliest-visible), and
two manifests sharing a `prev_manifest_cc` are a fork surfaced as conflict, never silently resolved.

**Scope — this is an ABSTRACT chain-completeness model, not an exact-manifest conformance checker.** It
verifies the *chain* (content-address recomputation + `prev_manifest_cc` reconstruction); it does not
verify `entries_root` / Merkle membership, which is a separate concern modelled here via a per-manifest
`contains` input kept **outside** the hashed `content` (so it never affects the cc). Most vectors use a
compact surrogate `content`; the **`exact-shape-*` control** carries the full normative §10 field set
(`profile, acceptance_head_cc, covered_through_seq, min_seq, max_seq, count, entries_root, prev_manifest_cc`,
with a real `entries_root` = Merkle over `H(JCS(entry))`) and proves the same `prev_manifest_cc`
recomputation over normative manifest bytes. 7 cases: two positive controls, the two required negatives,
genesis-fork and not-covered controls, and the exact-shape control; each guard reds independently under
mutation (missing-link-as-visible, forks-ignored, and a corrupted `prev_manifest_cc` on the exact-shape
manifest all break the right case).

## Run
```
python3 cutoff_enforce.py   pq-key-binding-v1.cutoff-vectors.json    # 9/9 reproduced
python3 manifest_resolve.py pq-key-binding-v1.manifest-vectors.json  # 6/6 reproduced
```

Provenance: zexoverz's ERC-8373 review (magicians #7) surfaced the v0 pre-cutoff rejection; the fix
already existed in the v1 profile and is live in the gateway. This lands it in the conformance suite.
