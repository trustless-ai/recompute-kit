# ERC-8275 win-rate basis-points coordinated completion matrix

Status: planning artifact only; no cutover is activated by this document.

Audit date: 2026-08-28

## Decision

The original basis-points cutover is already partially deployed. The remaining
work is therefore a coordinated **completion and compatibility window**, not a
greenfield switch and not a rollback:

- `trustless-ai/agent-sdk` already computes integer basis points in Go,
  Python, Rust, and TypeScript;
- the live `api.babyblueviper.com/ledger` reputation axis already publishes
  `winRateBps` with the target convention hash;
- `recompute-kit` now carries a prospective, hash-pinned BPS conformance lane,
  while its primary ERC-8275 `agent-flow` vectors and live recipe still run
  through the legacy four-decimal representation;
- `recompute-lens` and `trustless-agent-substrate` expose convention-unbound
  numeric results.

No component should independently declare the migration complete. Historical
artifacts are never rewritten, silently relabelled, or evaluated under a
current default.

## Exact identities

| Role | Exact identity | Rule | Observed use |
| --- | --- | --- | --- |
| Legacy registered convention | `0xf08010c434aa6affafb8f8976be12cab526471093e241c88f3218be2ac380227` | `win_rate.float-4dp.v0`; float in `[0,1]`, four decimal places, half-to-even | Registered by `convention-hash-v0`; no persisted-artifact reference found in the audited public repositories |
| Legacy `agent-flow` rule | `0xe4cccdfecd0a29a1703e51995883a27c58cd3edf07ea6a2070ffc912520644a5` | exact rational internally; four-decimal boundary, half-away-from-zero | Pinned by `conformance/agent-flow.vectors.json` and enforced by `bin/conformance` |
| Target convention | `0x0501b75db8e9ef4ef67c74efcfbe2a200b0a7e5aea5ca62f778c91c119e68daf` | `win_rate.bps.v0`; `(wins*20000 + total) // (2*total)`, integer `0..10000`, half-up | Shipped by `agent-sdk`; published by the live ledger; resolved by `recompute-kit` |

The two legacy hashes are not aliases. In particular, `0xe4…` hashes the
historical `agent-flow.rounding_convention.rule` object, while `0xf080…` hashes
a differently shaped convention specification with a different rounding mode.
A resolver MUST preserve that distinction and MUST NOT manufacture a new
preimage while retaining either old hash.

## Audited bases

| Surface | Exact audited head |
| --- | --- |
| `trustless-ai/recompute-kit` | `9461bf3f881484725f9730c5711fb1ff657356e4` (includes prospective BPS issuance lane from PR #28) |
| `trustless-ai/agent-sdk` | `aa76a2fe96c227ea67af11a1ff0d7e4bc7e682d3` |
| `trustless-ai/recompute-lens` | `70b44d854a32c867b756fa1272b194d4ae8f1ce0` |
| `trustless-ai/trustless-agent-substrate` | `a344ef80f7c52c03b9183814d1874b8054639c3e` (`feature/tas-poc`) |
| `babyblueviper1/invinoveritas` | `25a239afabc1bb5f066e0738e6a1a7a75535f0e5` plus the live `/ledger` response inspected on 2026-08-28 |
| `trustless-ai/ccip-router` | `84b235dbdd919d38d6b20c7e41351714f9a8e04f` |
| `pipavlo82/recomputable-verification-receipts` | `e1edd654fc8ae6cde1af18ec055959dbbb4066a0` |

## Current-state findings

### `recompute-kit`

- `mcp/conventions.py` resolves `0xf080…` and `0x0501…`, but not the distinct
  `0xe4…` identity used by the historical `agent-flow` suite.
- `conformance/agent-flow.vectors.json` still carries float expectations such
  as `0.5161` and pins `0xe4…` as a global `rounding_convention`.
- `bin/conformance` evaluates that legacy rule correctly with exact Decimal
  plus `ROUND_HALF_UP`.
- `bin/recompute-step 8275/reputation` still reads and compares the decimal
  `inputs.winRate`; it does not resolve the published
  `winRateBpsGoverningConventionHash`.
- PR #28 added `conformance/erc8275-win-rate-bps-v0` as a prospective issuance
  lane: 10 exact integer vectors, a derived `0x0501…` convention identity,
  distinct legacy-float mutation coverage, and fail-closed missing/unknown
  pointer controls. It did not change the legacy vectors or runtime recipe.

### `agent-sdk`

- Go, Python, Rust, and TypeScript compute the target integer BPS rule.
- `pinWinRateBps` emits `{value, governing_convention_hash}` with `0x0501…`.
- SDK-local `verifyWinRate` implementations recognize only `0x0501…`; they do
  not independently preserve either legacy verification path.
- The shared testkit vector still says `expected: 0.5161`. Language tests
  convert that float to `5161` before comparing, so the current green result is
  adapter conversion, not exact reproduction of one representation.
- Python and TypeScript ERC-8275 READMEs still document a float return value.

### Live Baby Blue Viper / Fede ledger

- The live reputation axis publishes `winRateBps` and the exact `0x0501…`
  convention hash.
- The live reputation axis is computed at request time. The `/ledger` response
  is not itself a persisted snapshot artifact.
- The same response retains a decimal `inputs.winRate` view.
- `track_record.win_rate_pct` is a separate presentation statistic with a
  different documented population/denominator. It MUST NOT be silently treated
  as the ERC-8275 decisive-only `winRateBps` value.
- No current persisted snapshot artifact on this surface carries a derived
  win-rate value, so there is no missing pointer to backfill. Prospectively, the
  convention pointer belongs on each newly persisted artifact that contains a
  derived convention-governed value. Raw outcome/evidence entries that contain
  no such derived value do not acquire a meaningless pointer.

### Downstream consumers

- `recompute-lens` performs exact integer half-up arithmetic internally, then
  formats the result back to a decimal string such as `0.5161`; it exposes no
  convention identity.
- `trustless-agent-substrate` pins `@trustless-ai/agent-sdk` `0.3.0` and exposes
  `computeWinRate` as a tool returning a bare JSON `number`; neither unit nor
  convention identity is in the output schema.
- `ccip-router` / TSEI Profile A has no win-rate or convention dependency.
- RVR and Crystal Receipt have no dependency on this migration.

## PR and owner matrix

Owners below are proposed from the current repository/component ownership and
must acknowledge their row before a completion date is announced.

| ID | Repository / deployment | Proposed owner | Required change | Depends on | Completion evidence |
| --- | --- | --- | --- | --- | --- |
| BPS-0 | `trustless-ai/recompute-kit` | recompute-kit maintainers; Pavlo and Baby Blue Viper/Fede review the identity boundary | Add an explicit resolver path for the exact `0xe4…` legacy rule without reinterpreting its preimage; retain `0xf080…` and `0x0501…`; prove all three remain distinct; unknown/missing identity stays `unverifiable` | none | Three positive resolution vectors, cross-convention negative controls, unknown-hash control, exact hash reproduction |
| BPS-1 | `trustless-ai/recompute-kit` | recompute-kit maintainers | **Partially landed:** PR #28 / `9461bf3…` added the dedicated prospective BPS conformance lane with integer expectations and per-vector convention identity while leaving the legacy lane unchanged. **Remaining:** update the live ERC-8275 recipe to resolve the artifact-declared hash before evaluation and bind that path to BPS-0 resolver closure | BPS-0 for remaining runtime work | Landed evidence: 10/10 BPS goldens and 10/10 mutation controls, including missing/unknown pointer failure and legacy-float distinction. Completion still requires the live recipe plus retained legacy goldens |
| BPS-2 | `trustless-ai/agent-sdk` | JimmyShi22 / agent-sdk maintainers | Replace float testkit expectations and test-side `×10000` conversions with exact BPS vectors; correct Go/Python/TS documentation; either resolve all supported legacy identities or explicitly delegate legacy verification to the pinned recompute-kit resolver | BPS-0 identity decision | Go/Python/Rust/TS reproduce the same exact vectors with no representation adapter; legacy policy is tested and documented |
| BPS-3 | `trustless-ai/recompute-lens` | TMerlini / recompute-lens maintainers | Make BPS the identity-bearing output (`valueBps` plus `governing_convention_hash`); keep decimal rendering presentation-only; resolve a supplied legacy hash instead of assuming the current rule | BPS-0, BPS-1 vectors | UI vectors show BPS identity, legacy resolution, unknown-hash `unverifiable`, and no bare ambiguous output |
| BPS-4 | `trustless-ai/trustless-agent-substrate` | JimmyShi22 / TAS maintainers | Expose the pin-aware SDK operation rather than bare `computeWinRate → number`; output `{value, governing_convention_hash}`; regenerate the manifest and package digests against the released SDK containing BPS-2 | BPS-2 release | Generated schema requires both fields; manifest/package integrity regenerated; tool conformance passes |
| BPS-5 | Baby Blue Viper/Fede live ledger and any future persisted derived artifact | Baby Blue Viper/Fede — acknowledged 2026-08-28 | Keep the already-live request-time BPS value/hash pair; record a prospective issuance rule that any future persisted artifact carrying the derived win-rate value also carries the pointer; do not manufacture or backfill an artifact that does not currently exist; keep `track_record.win_rate_pct` explicitly separate | BPS-0 semantics; BPS-1 verifier ready before such an artifact is issued | Current disposition is `PROSPECTIVE_NO_PERSISTED_ARTIFACT`; if a persisted artifact is later introduced, it independently recomputes to its pinned hash/value and no signed history is rewritten |
| BPS-6 | coordinated completion record | Pavlo coordinates; all blocking row owners acknowledge | Select one merge/deploy window only after BPS-0 through BPS-4 are ready and the acknowledged BPS-5 prospective disposition is recorded; record exact merged commits, released package integrity, deployment observation, and rollback/fail-closed procedure | BPS-0..BPS-4 ready; BPS-5 disposition recorded | Cross-component smoke vector passes from one exact input through SDK issuance, resolver, lens, and TAS; `BUILD_QUEUE.md` changes from unscheduled to completed with exact identities; no fictitious persisted-artifact leg is claimed |
| BPS-7 | `trustless-ai/agent-ercs` documentation | agent-ercs maintainers | Clarify that any concrete persisted win-rate representation must declare its unit/convention; do not make a specific off-chain implementation authoritative | non-blocking after BPS-0 | Documentation change only; no contract/interface change required |

## Merge and deployment order

1. **Resolver closure first — BPS-0.** No completion window may be scheduled
   until every real historical identity is resolvable or explicitly classified
   as unavailable without guessing.
2. **Prepare BPS-1 through BPS-4 without independent completion claims.** Each
   PR uses the exact hashes above and carries its own negative controls. BPS-5
   remains an acknowledged prospective issuance rule unless and until a
   persisted derived artifact is introduced.
3. **Release the corrected SDK before regenerating TAS.** BPS-2 produces one
   immutable package identity; BPS-4 pins that exact package.
4. **Merge consumers before declaring completion.** The family must be able to
   read both historical and target identities. There is no current persisted
   live-artifact pointer rollout to schedule; a future persisted derived
   artifact is issued under BPS-5 only after the verifier is ready.
5. **Run one cross-component smoke vector.** Recommended edge:
   `wins=1, losses=31`, where the target result is `313` BPS and the historical
   four-decimal result is `0.0313`. The values can look related while remaining
   different typed representations and different identities.
6. **Record completion, do not rewrite history.** Update the queue with exact
   merge commits, package integrity, deployment observation, and the retained
   legacy resolution evidence.

## Historical-artifact rule

- A signed or content-addressed artifact is never modified to add a pointer.
- A missing pointer is not inferred from its numeric shape, date, repository,
  current default, or apparent decimal scale.
- An immutable enclosing package may bind an old pointer only when that binding
  was already part of the package's authority or is explicitly represented as
  a new wrapper/verification artifact; it does not retroactively alter the
  original artifact.
- Unknown or unavailable convention identity produces `unverifiable`, never a
  guessed value, rejection under the current rule, or silent conversion.

## Go/no-go checklist

- [ ] BPS-0 independently reproduces and resolves all three exact identities.
- [ ] The `0xe4…` legacy preimage is preserved exactly and is not recast as the
      `0xf080…` schema.
- [x] The prospective BPS lane contains integer expected values and no adapter
      multiplication (PR #28 / `9461bf3…`).
- [x] BPS-5 owner confirmed that `/ledger` is a request-time view and that no
      current persisted derived win-rate artifact requires a pointer or
      backfill; the future issuance rule is acknowledged.
- [ ] Every newly persisted derived win-rate value carries its convention hash.
- [ ] Every consumer reads the artifact-declared identity before recomputation.
- [ ] Missing/unknown identity fails closed.
- [ ] Old float artifacts remain verifiable under their exact rule where the
      required bytes are available.
- [ ] `track_record.win_rate_pct` remains explicitly outside the ERC-8275 BPS
      identity.
- [ ] Exact SDK package integrity and every merged commit are recorded.
- [ ] Cross-component `1/31` smoke vector passes before completion is announced.
- [ ] All proposed owners acknowledge their row and the completion window.

Until every blocking item above is checked, the status remains:

```text
BASIS_POINTS_COORDINATED_COMPLETION: NOT SCHEDULED
```
