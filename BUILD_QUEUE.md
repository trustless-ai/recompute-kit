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
