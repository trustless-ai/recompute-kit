# pq-recovery-classes.v0 — recomputable authority transitions for per-agent PQ keys

A per-agent post-quantum key scheme is only *survivable past a single incident* if an independent third
party can tell, **from the anchored trail alone**, which kind of authority transition happened — and can be
**wrong on purpose** when a record doesn't match its label. This profile pins three classes as falsifiable
claims. Companion to `pq-key-binding-v0` (the binding + cutoff enforcer); this is the recovery layer above it.

Blind-diff artifact for the design agreed 2026-07-31 with **babyblueviper1** (Fede) and **pipavlo82** (Pavlo);
`recovery_check.py` derives every verdict from the predicate alone. Run: `python3 recovery_check.py vectors.json` → **11/11**.

## The three classes

| class | verdict | predicate (what a third party recomputes) | authority domain |
|---|---|---|---|
| `rotation` | `continuity` | the named `superseded_by` binding **exists** in the anchored history, is **in force** from ≥ this anchor time, and is **not revoked** | per-agent · SIWE owner |
| `agent_terminal` | `terminated` | **no** binding can resolve in force for **any** t after this anchor time (every epoch's authority has ended) | per-agent · SIWE owner |
| `seed_epoch_rotation` | `systemic_recovery` | every new per-agent key equals `derive(S', registry, agent_id)`, **and** the statement is anchored under an identity that provably does **not** derive from any seed | fleet · deployer-tx |

A record is judged **only against its declared class**. If the predicate fails the verdict is `rejected` —
**never** silently reinterpreted as an adjacent class. The `vectors.json` makes that explicit: a rotation
whose successor is absent fails *as a rotation* (not "read as a kill"); a kill with a surviving in-force
epoch fails *as a kill* (not "degrade into a rotation"). That cross-class safety is what makes the three
genuinely distinguishable rather than merely differently named.

## Two structural decisions, made recomputable

**1. Authority for replacing a compromised root cannot reduce to the thing being replaced.** Same shape as
anchor-time over signature-time in `pq-key-binding-v0`: the trustworthy quantity is the one the operator
can't forge after the fact. A seed rotation authorized under the seed it replaces is forgeable by whoever
compromised the seed. So `seed_epoch_rotation` rests on the **classical deployer key** (`0xFf9a…`), whose
control is proven by the **`record()` transaction sender itself** (`auth.anchor_tx_from == auth.identity ==
DEPLOYER`) — a possession proof that can't be omitted, not a separable signature. (Pavlo's point: the
deployer key isn't chosen for extra strength; it's chosen because its possession is *already anchored*.)

**2. Authority domains are in the predicate, not a convention.** `rotation` and `agent_terminal` are
per-agent and owner-authorized (SIWE). `seed_epoch_rotation` is fleet-scoped. If the fleet class could be
authorized down the per-agent path, a **single compromised per-agent key would gain fleet-wide reach** — the
most powerful class inheriting the weakest authorization. The `seed_epoch_rotation` predicate therefore
checks the authority *domain*, not just key derivation: a fleet statement presented under `siwe_owner` is
`rejected` (see `seed_falsify_siwe_domain_violation`). Domain separation is recomputed, not assumed.

## Explicitly out of scope (stated, not silent)

**What authorizes replacing the deployer key itself is outside this recompute profile.** It is not an
infinite regress — the honest boundary is: *deployer-key compromise sits outside `pq-recovery-classes.v0`*.
A verifier of this profile can independently confirm rotation / kill / seed-recovery; it cannot adjudicate a
compromise of the classical anchor identity, and does not claim to. Unstated roots are exactly what surface
under pressure, so the root is named here rather than left implicit.

## Notes
- `derive(seed_epoch, registry, agent_id)` in the checker is the pinned key-derivation **shape** (a
  deterministic function of the seed epoch + identity), not the live master seed. Deployment uses
  `ml_dsa65.keygen(sha256(MASTER_SEED:registry:agent_id:seed_epoch))`; the profile fixes the predicate.
- `in_force` / revocation semantics are byte-identical to the live enforcer (`pqCutoff.ts` /
  `cutoff_enforce.py`): a binding governs from its anchor time; `revoked_at` ends its authority.
- Status: **vector-first, pre-implementation.** Rotation + revocation are live (`pq-key-binding-v0`);
  `agent_terminal` and `seed_epoch_rotation` are specified here and blind-diffed before either side wires
  them live.
