# Permission consumption: current validity composition v0

Profile: `permission_consumption_boundary.v0`.
Audited dependency base: `e3ed86f46f627885fc7e49b651796b194da46deb` in
`trustless-ai/recompute-kit`. Supplied finite deterministic histories only.

```text
HISTORICALLY VALID CHECK OF GRANT G / EPOCH E
!= VALID CONSUMPTION OF THE SAME G / EPOCH E UNDER CURRENT STATE
```

This is a composition boundary, not another expiry, revocation or capacity
implementation. There is one historical CHECK, completed supplied transitions,
and one later CONSUME. No threads, network calls or ambient clock are used by
this profile. An observed admit is retained even when the required outcome is
reject. CONSUME does not secretly mutate capacity or simulate a writer.

## Direct reuse

The checker loads these unmodified repository files using `runpy.run_path`
without executing their CLI main blocks. No formula is copied locally.

| Component | Actual callable | Composition |
| --- | --- | --- |
| Expiry | `bin/conformance::recompute`, step `mcp/entitled` | Called at CHECK time and independently at CONSUME time. The inherited rule is `expiry == 2**64-1 OR expiry > now`. Finite equality rejects. |
| Lifecycle | `conformance/captured-admission-v0/admission_check.py::authority` | The exact `[grant_id,grant_epoch]` is encoded as the authority epoch. Claims at each evaluation time use that same epoch. Activation and visible revoked/superseded transitions are handled by the original evaluator. |
| Capacity | `conformance/consumption-time-state-binding-v0/binding_check.py::predicate` and `state_valid` | The selected grant's domain supplies the current state; the actual predicate evaluates `used + amount <= ceiling`. State shape validation is also imported. |

The lifecycle adapter supplies the same constructed identity to capture and
admission binding fields. This is coordinate plumbing, not evidence of capture
or signature authenticity. It passes `expiry=None` to the authority evaluator
deliberately: expiry belongs to the independently observable entitlement axis,
and must not be checked twice in a way that masks removing that composition leg.
`attributed` means lifecycle satisfied for a claim at that evaluation time;
`out_of_authority` and `epoch_not_yet_active` mean violated. Invalid/conflicting
lifecycle evidence means cannot_establish. The inherited terminal-transition and
no-rollback rules are not reimplemented here. Supersession uses the core's default
policy; no bound-successor requirement or delegation chain is claimed.

P6 calls the same authority evaluator with the original claim time and later
`as_of`. It verifies that a now-revoked lifecycle still attributes the earlier
claim. This is an assertion over P5, not an extra copy of its history.

Other inspected primitives remain dependencies by reference only:
`mcp/entitled-at-action` also checks event-position precedence, which these scalar
time histories do not model; `ace/entitlement-binding` commits snapshots;
`ace/precedence` establishes ordering knowledge; `verdict/entitlement-drift`
classifies already-computed entitlement values. None must be mistaken for the
selected durable-grant composition. ERC-8312 conservation and aggregate-budget
root accounting concern budget/substrate relations; shared-parent delegation is
outside this profile. The imported #46 predicate suffices for this single-domain
capacity seam. #42's `profile-commitment-loop-v0/loop_gate.py` is the composition
precedent: use computed component results, not parallel asserted constants.

## Input contract and evidence

`vectors.json` contains cases with `inputs` and independently declared complete
`expected` results. Each input contains:

- `grant_id`, `grant_epoch`: the historically selected identity; nonempty string
  plus nonnegative integer epoch, unique among `grants`.
- `amount`: one immutable nonnegative integer throughout this history. No
  target, tool, function, argument policy or requested-versus-granted scope.
- `check_at`: historical evaluation time, a nonnegative integer.
- `grants`: immutable records with identity, `activated_at`, uint64 `expiry`,
  and `capacity_domain` (nonempty string or explicit null). Null explicitly means
  capacity is not required. A grant is not introduced by searching for whichever
  record happens to pass at consumption. Expiry must permit activation under the
  imported entitlement rule.
- `lifecycle_transitions`: supplied grant/epoch, kind and time. The core selects
  visible events at each as_of, so future revocation cannot alter the earlier
  check. Records for other grants/epochs cannot invalidate or rescue this one.
- `capacities`: unique domain identities, initial #46 state and completed ordered
  transitions with `at` and replacement state. Initial state applies from time 0;
  transition times strictly increase per domain and versions advance exactly one.
  Transitions at an evaluation time precede that evaluation. Outcome-affecting
  values may change or return to old values; versions do not roll back.
- `consume`: explicit grant/epoch/domain reference, time at or after CHECK,
  `observed_outcome` (`admit` or `reject`), and evidence-availability flags for
  expiry, lifecycle and capacity.

The evidence flags mean the corresponding current input/history is available
and complete **as a fixture assumption**. They do not assert freshness or a
predicate result. If true, the actual value is recomputed. If false, the component
is cannot_establish even when the omniscient fixture supplies values elsewhere.
For expiry this covers unavailable current clock/expiry evidence. For lifecycle
it covers unavailable complete transition history, rather than treating an empty
but incomplete list as proof of no revocation. For a capacity-required grant it
covers unavailable linked current state; an absent domain also cannot establish
capacity. A null capacity policy needs no such evidence (P22).

These are declared closed histories, not discovery/authentication of live state.
Grant records, clock coordinates, state versions, complete-history claims and
legitimacy of transitions are trusted supplied inputs. The checker cannot detect
omitted real events or a dishonest source asserting completeness.

All object member sets are explicit; malformed shapes/types, duplicate grant or
domain identities, invalid state/version progression and missing historical grant
evidence fail closed. JSON booleans are not numeric coordinates. All times have a
single supplied ordering; cross-chain clock policy is not modeled.

## Decisions and evaluation order

1. Validate the history and locate the selected historical G/E.
2. Compute historical expiry, lifecycle and capacity. Here `historical_check_status`
   means authorization held at CHECK, not merely that someone truthfully reported
   a false predicate. If it did not hold, current authorization is cannot_establish
   with `CURRENT_AUTHORIZATION_NOT_EVALUATED`; no claim of a valid PASS going stale.
3. Require CONSUME to name exactly the checked G/E and its bound capacity domain.
4. Independently recompute all required current components for that same identity.
5. Within either conjunction, a witnessed violation outranks unknown evidence;
   otherwise missing evidence remains cannot_establish. All satisfied means satisfied.
6. Admit is required only when both historical and current authorization are
   satisfied. All other combinations require reject.

```text
current_authorization_status = cannot_establish
required_consumption_outcome = reject
```

This operational fail-closed rule does not relabel unknown evidence as violated.
`observed_consumption_outcome` is never rewritten. The separate
`consumption_conformance_status` compares observed and required decisions: an
unknown authorization followed by observed admit violates the operational rule
while the authorization status stays unknown. The model also reports an observed
reject of established authority as a mismatch; it makes no production availability
claim. Invalid histories may have observed outcome `none`.

## Histories and falsifiability

There are 21 histories and one independent P6 assertion, not 22 histories.

| Case | Required distinction |
| --- | --- |
| P1 / P2 | Unchanged finite / perpetual grants legitimately admit. |
| P3 | Time advances from 5 to 15 with expiry 10, unchanged G/E: old PASS rejects. Version/epoch equality alone does not cover time. |
| P4 | Exactly `now == expiry` rejects under the inherited strict inequality. |
| P5 / P6 assertion | Revoked selected epoch cannot authorize now; historical attribution remains valid. |
| P7 / P8 | Valid renewed epoch / unrelated grant cannot rescue the checked expired identity. |
| P9 | G/E bound to C1; completed v7 used=0 to v8 used=6 transition makes amount=6 invalid. Same serialized shape as #46 S2. |
| P10 | Changed state still has room for amount=2: current evaluation admits. |
| P11 | C1 exhausted, C2 free: only the grant-linked C1 is relevant. |
| P12 / P13 / P14 | Missing current expiry / lifecycle / required capacity evidence is unknown, with required reject. |
| P15 | Already-expired at CHECK: historical violated; current not evaluated. |
| P16 | Missing evidence with observed admit retains unknown authorization and operational violation. |
| P17 / P18 / P19 | Direct consumed grant / epoch / domain mismatch rejects. |
| P20 | Known revocation outranks unknown capacity without erasing either component. |
| P21 | Conflicting terminal lifecycle evidence is unknown, not active or a guessed terminal. |
| P22 | Explicit policy with no capacity requirement remains admissible. |

`mutation_check.py` applies each source replacement exactly once in a temporary
in-memory module, never editing dependencies. All required killers must change
current authorization to satisfied and required reject to admit while preserving
historical results and observed behavior. Full expected results of all four
positive controls P1/P2/P10/P22 must remain identical. Crashes, import/compile
failures, unapplied mutations and control failures are separate unsuccessful
outcomes. There are no runtime mutation switches in the checker.

| Mutation | Required killers |
| --- | --- |
| M1 trust historical PASS | P3, P5, P9 |
| M2 check expiry only at CHECK time | P3, P4 |
| M3 ignore current lifecycle | P5 |
| M4 allow renewed epoch substitution | P7 |
| M5 allow unrelated grant substitution | P8 |
| M6 ignore current capacity | P9 |
| M7 allow unrelated capacity domain | P11 |
| M8 promote missing evidence to authorization | P12, P13, P14 |
| M9 allow consumed identity mismatch | P17, P18 |
| M10 allow consumed capacity domain mismatch | P19 |

No nonretroactivity mutation is added: historical results are computed once
before the current phase; P6 independently pins nonretroactivity without
inventing a current-to-historical assignment solely to mutate it.

## Relationship to #46 and limits

This profile does NOT supersede or modify #46.

```text
#46: EVENT-TIME PASS != CONSUMPTION-TIME STATE VALIDITY
Here: HISTORICALLY VALID DURABLE GRANT G/E
      != CURRENTLY AUTHORIZED CONSUMPTION OF THAT SAME G/E
```

#46 S2 separates a historical state-dependent PASS from later stale consumption.
S10/M6 binds the checked request coordinate to the consumed amount. S11 separates
restored numeric values from old state identity (ABA). Those distinctions remain
unchanged; this profile imports capacity evaluation and adds selected durable
grant/lifecycle/time composition. It does not duplicate S10 into Family B.

No claim of production wallet enforcement, ERC-7715 compliance, ERC-8004
enforcement, production permission safety, live chain state authenticity,
signature authenticity, concurrency safety, atomicity, serialized writer
enforcement, exactly-once delivery, replay protection, idempotency, target
authorization, function authorization, argument authorization, requested-versus-
granted scope correctness, delegation ancestor validity, shared-parent delegation
correctness, complete authority graph discovery, real Fede decision_ref
compatibility, or a proven production vulnerability follows. No Robinhood or
Semantic Execution Guard integration is included.

## Reproduction

From repository root (Python 3, no new dependencies):

```sh
python3 conformance/permission-consumption-boundary-v0/permission_check.py conformance/permission-consumption-boundary-v0/vectors.json
python3 conformance/permission-consumption-boundary-v0/mutation_check.py
python3 -O conformance/permission-consumption-boundary-v0/permission_check.py conformance/permission-consumption-boundary-v0/vectors.json
python3 -O conformance/permission-consumption-boundary-v0/mutation_check.py
python3 tools/run_conformance.py
```

Repeated and optimized complete reports must be byte-identical. `suite.json`
uses automatic suite discovery; no existing index/runner is edited. Spec, checker,
mutation checker, vectors and imported sources have mechanically generated SHA-256
pins. The canonical runner validates its supported spec/vector pins; checker and
dependency metadata pins require explicit validation, not an inferred runner claim.
