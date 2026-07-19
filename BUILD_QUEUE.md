# BUILD_QUEUE

Deferred design notes — not urgent, but load-bearing when their moment comes. Pinned here so they survive between now and then.

---

## Rounding-convention migration (basis-points): pin at issuance, resolve at verification

**When:** whenever `winRate` (and any rounded value) migrates from the ROUND_HALF_UP-over-`Decimal` bridge to integer **basis-points** — the endpoint that removes rounding by construction (see `CONVENTIONS.md`). Not urgent; logged so it isn't lost between now and the actual migration.

**Why it's not a cleanup:** the rounding rule now carries a content-hash (`rounding_convention` in `conformance/agent-flow.vectors.json`). Changing it is a change to a **declared derivation rule**, not a refactor. A receipt/vector derived under the current convention stays valid **only under the convention it declared** — a silent swap breaks every artifact that used the bridge.

**The discipline (Pavlo + Fede, 2026-07-19 thread):**

1. **New entry, old one stays.** Basis-points ships as a *new* `rounding_convention` entry — its own `rule`, its own `hash`, its own `governs` scope. The old entry stays in the file; never overwrite or silent-swap. (Extends the pattern the `version` field + `governs` list already set up.)
2. **The pointer belongs in the artifact, not the file.** Every vector/artifact pins the convention hash that governed it **at issuance**. The file is where conventions are *looked up*; the artifact declares which one *governed it*. Same shape as `ruleset_version`.
3. **Resolve at verification.** A verifier reading an older artifact resolves **its** declared convention hash, recomputes under **that** rule, and only then compares — never "whatever's declared today."
4. **Fails-closed.** Unknown or missing convention pointer → **unverifiable**, never a guess. Same instinct as unknown-opset (attester independence) and the `/verify` amber state.

**One-liner (Pavlo):** *pinned at issuance, resolved at verification.*

**Status (2026-07-19):** direction ratified by all SDK authors (Jimmy, Fede, Pavlo, Tiago) — basis-points is the agreed target, not an open proposal. Jimmy is refining the Rust SDK design plans around it. **Cutover must be coordinated**: every SDK (Rust + TS reference) switches together, each pinning the new convention hash — a half-migrated family reintroduces exactly the cross-SDK mismatch this guards against. Still not urgent; no cutover scheduled.

---

## ACE cross-chain precedence: `entitled_at` indeterminate state + `precedence_policy` allowlist

**When:** once Pavlo pins the `precedence_policy` shape + the three Δ vectors (same-chain Δ=0 determinate / cross-chain outside Δ determinate / cross-chain inside Δ indeterminate). Deferred — not urgent, no code until the policy shape + goldens land (don't retrofit `entitlement_binding.v0` — `precedence_policy` is a v1 field that regenerates every hash).

**Why:** the fully-recomputable licensed-MCP audit orders a grant against an action by their on-chain positions. When grants and action anchors sit on **different chains** (our mainnet registry × Base-Sepolia per-action anchors) and their timestamps fall inside the skew bound Δ, precedence is *not* false — it's **unestablished-from-here**. The honest output is indeterminate, which must flow to the drift `unverifiable` row (= `ace-drift-unreadable`) and Fede's `vantage_limitation`, never a guessed ordering.

**The shape (Pavlo, two-sided — same as canonicalization):**
1. **Issuer declares.** `precedence_policy: { profile, delta_seconds, basis }` is pinned in the binding at issuance and **covered by `binding_hash`**. A verifier resolves *that artifact's* Δ, never today's. `basis` reports provenance, not an assertion: `same-chain` ⇒ Δ=0 (block order is total); `l2-l1` ⇒ Δ derivable from finality; `independent-chains` ⇒ Δ=∞ (precedence never established).
2. **Consumer pins what it recognizes.** The verifier carries a list of accepted precedence profiles. Unrecognized profile → **unverifiable**; declared Δ below what the consumer deems sound for that chain pair → **unverifiable**. Same fails-closed as an unrecognized c14n profile — the issuer can declare anything, it doesn't buy admission.

**Build when it lands:**
- `mcp/entitled-at-action` (+ the drift path): return a third **indeterminate** state when the grant/action pair is cross-chain and inside Δ, instead of forcing true/false. It routes to `unverifiable`.
- Consumer-side `precedence_policy` allowlist check (unrecognized/insufficient → unverifiable).
- Gate against Pavlo's three vectors; the cross-chain-inside-Δ one is the whole point, the other two prove it doesn't over-fire.

**Vértice's pricing (declared 2026-07-19):** the mainnet-grants / Base-anchors split is load-bearing (the registry family lives on mainnet; Base carries per-action gas), so we declare `basis:"independent-chains", delta_seconds:∞` for that pair — the indeterminate window is a **known, declared cost**, not a surprise at the boundary. Same-chain Δ=0 is the escape hatch if we ever co-locate. Credit: Pavlo (Δ two-sided shape), Fede (`vantage_limitation` home).

**Status (2026-07-19):** `precedence-v0` policy + recipes LANDED in recompute-kit v0.12 — `ace/entitlement-binding` now folds `precedence_policy` into `binding_hash` (delta_seconds a decimal STRING or `"unbounded"`, per Pavlo's serialization catch), and `ace/precedence` gates the 4 evaluation outcomes (same-chain / cross-outside-Δ determinate, cross-inside-Δ / independent-unbounded indeterminate). Pavlo's goldens reproduced independently (e57c8bfd… / 286155e1… shared / e680c9cc…). **Still deferred: the GATEWAY-side live wiring** — `entitledAtAction` emitting the `indeterminate` state on a cross-chain-inside-Δ pair (currently uses a single recorded clock so it's determinate today) + the consumer-side `precedence_policy` allowlist (unrecognized profile / insufficient Δ → unverifiable). Fede verified the entitlement_binding composition byte-for-byte (artifact_hash == binding_hash, no schema change) — composition is WIRED.

**Status (2026-07-19, later):** GATEWAY WIRING LANDED too — the licensed-MCP audit now declares its `precedence_policy` in the recompute output, evaluates precedence per action (mirroring `ace/precedence`), and routes an indeterminate cross-chain pair to `entitled_at=null → unverifiable`. Default is `same-chain`/Δ=0 (the audit orders on a single recorded clock, determinate — demo stays useful); set `MCP_ACTION_CHAIN_ID` + `MCP_PRECEDENCE_BASIS=independent-chains`/`MCP_PRECEDENCE_DELTA=unbounded` and it flips to the fully-recomputable cross-chain stance (verified: rows read `indeterminate`, reverted). Surfaced on `/console`. Remaining truly-open: the consumer-side precedence-profile *allowlist* (unrecognized profile → unverifiable) belongs on the /review verifier (Fede's layer), not ours. **This item is effectively closed on the ACE/Vértice side.**
