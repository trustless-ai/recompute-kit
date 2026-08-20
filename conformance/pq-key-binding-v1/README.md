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

## Run
```
python3 cutoff_enforce.py pq-key-binding-v1.cutoff-vectors.json   # 9/9 reproduced
```

Provenance: zexoverz's ERC-8373 review (magicians #7) surfaced the v0 pre-cutoff rejection; the fix
already existed in the v1 profile and is live in the gateway. This lands it in the conformance suite.
